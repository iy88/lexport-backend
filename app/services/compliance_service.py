import hashlib
import os
import uuid
import zipfile

from openai import OpenAI
from flask import current_app
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.agency import Agency
from app.models.diagnosis import DiagnosisRecord, DiagnosisResult
from app.utils.errors import AppError, NotFoundError, ValidationError
from app.utils.oss_utils import delete_object, generate_signed_url, upload_file
from app.utils.report_utils import InvalidReportError, apply_report_metadata


ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.html'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_FILES = 5

REQUIRED_FIELDS = [
    'query', 'company_name', 'industry', 'company_size',
    'target_country', 'business_model', 'budget_range',
]


def _cleanup_tmp_files(file_paths):
    """Remove local temporary files."""
    for p in file_paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass


def _validate_file_signature(local_path, ext):
    """Require the file contents to match the submitted extension."""
    with open(local_path, 'rb') as source:
        header = source.read(8)

    if ext == '.pdf' and not header.startswith(b'%PDF-'):
        raise ValidationError('PDF 文件内容与扩展名不匹配')
    if ext == '.doc' and header != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        raise ValidationError('DOC 文件内容与扩展名不匹配')
    if ext == '.docx':
        try:
            with zipfile.ZipFile(local_path) as archive:
                names = set(archive.namelist())
                if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
                    raise ValidationError('DOCX 文件结构无效')
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValidationError('DOCX 文件内容与扩展名不匹配') from exc
    if ext in ('.txt', '.html'):
        try:
            with open(local_path, 'rb') as source:
                content = source.read()
            if b'\x00' in content:
                raise ValidationError('文本文件包含二进制内容')
            content.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValidationError('文本文件必须使用 UTF-8 编码') from exc


def _save_tmp_file(file_storage):
    """Validate and stage one upload; return path/name/key/size/hash metadata."""
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f'不支持的文件类型: {ext}')
    secure_name = str(uuid.uuid4()) + ext
    tmp_dir = os.path.join(current_app.config['UPLOAD_PATH'], 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, secure_name)

    total_size = 0
    file_hash = hashlib.sha256()
    try:
        try:
            file_storage.stream.seek(0)
        except (AttributeError, OSError):
            pass
        with open(local_path, 'wb') as output:
            while True:
                chunk = file_storage.stream.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise ValidationError('单个文件不能超过 20MB')
                output.write(chunk)
                file_hash.update(chunk)
        _validate_file_signature(local_path, ext)
    except Exception:
        try:
            os.remove(local_path)
        except OSError:
            pass
        raise

    return (
        local_path,
        file_storage.filename,
        secure_name,
        total_size,
        file_hash.hexdigest(),
    )


def _build_relative_agency(target_country):
    """Build relative_agency string from published agencies matching the target country."""
    agencies = (
        Agency.query
        .filter(Agency.status == 'published', Agency.region.contains(target_country))
        .order_by(Agency.sort_order)
        .all()
    )
    if not agencies:
        return ''

    lines = [
        f'机构名称：{a.name}，适配业务：{a.business or "无"}，'
        f'核心优势：{a.advantage or "无"}'
        for a in agencies
    ]
    return '\n'.join(lines)


def _report_settings():
    """Validate report configuration without constructing an external client."""
    app_id = current_app.config['REPORT_GENERATOR_APPID'].strip()
    if not app_id:
        raise AppError('CONFIG_ERROR', '报告生成服务未配置', 500)
    api_key = current_app.config['BAILIAN_API_KEY'].strip()
    if not api_key:
        raise AppError('CONFIG_ERROR', '报告生成服务未配置', 500)
    if not current_app.config['REPORT_AI_VERSION'].strip():
        raise AppError('CONFIG_ERROR', '报告 AI 版本未配置', 500)
    if not current_app.config['REPORT_DATA_CUTOFF_DATE'].strip():
        raise AppError('CONFIG_ERROR', '报告数据截止日期未配置', 500)

    return {
        'app_id': app_id,
        'api_key': api_key,
        'ai_version': current_app.config['REPORT_AI_VERSION'].strip(),
        'data_cutoff_date': current_app.config['REPORT_DATA_CUTOFF_DATE'].strip(),
    }


def _get_bailian_client(timeout=None, max_retries=None):
    """Create an OpenAI-compatible client pointed at Bailian."""
    settings = _report_settings()
    app_id = settings['app_id']
    api_key = settings['api_key']

    configured_url = current_app.config['BAILIAN_BASE_URL'].strip().rstrip('/')
    if '/api/v2/apps/agent/' in configured_url:
        base_url = configured_url + '/'
    else:
        generic_suffix = '/compatible-mode/v1'
        if configured_url.endswith(generic_suffix):
            configured_url = configured_url[:-len(generic_suffix)]
        base_url = (
            f'{configured_url}/api/v2/apps/agent/{app_id}'
            '/compatible-mode/v1/'
        )

    client_args = {
        'base_url': base_url,
        'api_key': api_key,
    }
    if timeout is not None:
        client_args['timeout'] = timeout
    if max_retries is not None:
        client_args['max_retries'] = max_retries
    return OpenAI(**client_args)


def _compute_fingerprint(form, doc_meta):
    """Hash canonical form values and validated attachment metadata."""
    h = hashlib.sha256()
    for field in REQUIRED_FIELDS:
        h.update(field.encode('utf-8'))
        h.update(b'\x00')
        h.update((form.get(field, '') or '').strip().encode('utf-8'))
        h.update(b'\x00')
    for original_name, _, size, content_hash in doc_meta:
        h.update((original_name or '').encode('utf-8'))
        h.update(b'\x00')
        h.update(str(size).encode('utf-8'))
        h.update(b'\x00')
        h.update(content_hash.encode('ascii'))
        h.update(b'\x00')
    return h.hexdigest()


def _build_biz_params(form):
    """Build biz_params dict from validated form fields."""
    query = form['query'].strip()
    company_name = form['company_name'].strip()
    industry = form['industry'].strip()
    company_size = form['company_size'].strip()
    target_country = form['target_country'].strip()
    business_model = form['business_model'].strip()
    budget_range = form['budget_range'].strip()
    relative_agency = _build_relative_agency(target_country)
    return query, company_name, industry, company_size, target_country, business_model, budget_range, relative_agency


def create_report(user, form, files, idempotency_key):
    """Validate, upload to OSS, call Bailian, and persist a DiagnosisRecord.

    Returns ``(record, replayed)``.  All local/file validation is completed
    before the idempotency reservation or any external request.
    """
    if not user.email or not user.email_verified:
        raise AppError(
            'EMAIL_VERIFICATION_REQUIRED',
            '请先验证邮箱后再创建合规报告',
            403,
        )

    missing = [f for f in REQUIRED_FIELDS if not (form.get(f) or '').strip()]
    if missing:
        raise ValidationError(f'缺少必填字段: {", ".join(missing)}')

    query, company_name, industry, company_size, target_country, \
        business_model, budget_range, relative_agency = _build_biz_params(form)

    field_limits = {
        'target_country': (target_country, 30),
        'company_size': (company_size, 20),
        'business_model': (business_model, 20),
        'budget_range': (budget_range, 20),
    }
    oversized = [name for name, (value, limit) in field_limits.items() if len(value) > limit]
    if oversized:
        raise ValidationError(f'字段长度超过限制: {", ".join(oversized)}')

    settings = _report_settings()
    report_ai_version = settings['ai_version']
    report_data_cutoff_date = settings['data_cutoff_date']

    uploaded_files = files.getlist('documents') if files else []
    uploaded_files = [file for file in uploaded_files if file.filename]
    if len(uploaded_files) > MAX_FILES:
        raise ValidationError(f'最多上传 {MAX_FILES} 个文件')

    tmp_paths = []
    oss_objects = []
    doc_meta = []  # (original_name, secure_name, size, sha256)
    record = None
    reserved = False

    try:
        # Validate and stage every attachment before reserving the paid request.
        for f in uploaded_files:
            local_path, original_name, secure_name, size, content_hash = _save_tmp_file(f)
            tmp_paths.append(local_path)
            doc_meta.append((original_name, secure_name, size, content_hash))

        fingerprint = _compute_fingerprint(form, doc_meta)
        existing = DiagnosisRecord.query.filter_by(
            user_id=user.id,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            if existing.request_fingerprint == fingerprint:
                return existing, True
            raise AppError(
                'IDEMPOTENCY_CONFLICT',
                '相同的 Idempotency-Key 对应不同的请求内容',
                409,
            )

        reservation_biz_params = {
            'company_name': company_name,
            'industry': industry,
            'company_size': company_size,
            'target_country': target_country,
            'business_model': business_model,
            'budget_range': budget_range,
            'documents': [{'name': meta[0]} for meta in doc_meta],
            'relative_agency': relative_agency,
        }
        record = DiagnosisRecord(
            user_id=user.id,
            country=target_country,
            company_size=company_size,
            budget_range=budget_range,
            business_model=business_model,
            status='submitting',
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            param={
                'input': query,
                'biz_params': reservation_biz_params,
                'report_meta': {
                    'ai_version': report_ai_version,
                    'data_cutoff_date': report_data_cutoff_date,
                },
            },
        )
        db.session.add(record)
        try:
            db.session.commit()
            reserved = True
        except IntegrityError:
            db.session.rollback()
            existing = DiagnosisRecord.query.filter_by(
                user_id=user.id,
                idempotency_key=idempotency_key,
            ).first()
            if not existing:
                raise
            if existing.request_fingerprint != fingerprint:
                raise AppError(
                    'IDEMPOTENCY_CONFLICT',
                    '相同的 Idempotency-Key 对应不同的请求内容',
                    409,
                )
            return existing, True

        for _, secure_name, _, _ in doc_meta:
            local_path = os.path.join(current_app.config['UPLOAD_PATH'], 'tmp', secure_name)
            try:
                upload_file(local_path, secure_name)
                oss_objects.append(secure_name)
            except AppError as exc:
                raise AppError(
                    'OSS_UPLOAD_FAILED',
                    '文件上传至 OSS 失败，请稍后重试',
                    502,
                ) from exc

        doc_urls = []
        for _, secure_name, _, _ in doc_meta:
            try:
                url = generate_signed_url(secure_name)
            except AppError as exc:
                raise AppError(
                    'OSS_UPLOAD_FAILED',
                    '文件签名失败，请稍后重试',
                    502,
                ) from exc
            doc_urls.append({'url': url})

        biz_params = {
            'company_name': company_name,
            'industry': industry,
            'company_size': company_size,
            'target_country': target_country,
            'business_model': business_model,
            'budget_range': budget_range,
            'documents': doc_urls,
            'relative_agency': relative_agency,
        }

        try:
            client = _get_bailian_client()
            response = client.responses.create(
                input=query,
                background=True,
                extra_body={'biz_params': biz_params},
            )
        except Exception as exc:
            current_app.logger.exception('Failed to create Bailian report task')
            raise AppError('BAILIAN_ERROR', '调用百炼失败，请稍后重试', 502) from exc

        initial_status = response.status
        if initial_status not in ('queued', 'in_progress', 'completed', 'failed', 'cancelled'):
            initial_status = 'in_progress'

        record.task_id = response.id
        record.status = initial_status
        record.param = {
            'input': query,
            'biz_params': biz_params,
            'report_meta': {
                'ai_version': report_ai_version,
                'data_cutoff_date': report_data_cutoff_date,
            },
        }

        invalid_completed = False
        if initial_status == 'completed':
            try:
                result_data = apply_report_metadata(
                    response.model_dump(mode='json'),
                    record.id,
                    report_ai_version,
                    report_data_cutoff_date,
                )
                db.session.add(DiagnosisResult(
                    record_id=record.id,
                    result=result_data,
                ))
            except InvalidReportError:
                current_app.logger.exception(
                    'Bailian returned invalid report JSON for record %s',
                    record.id,
                )
                record.status = 'failed'
                invalid_completed = True

        db.session.commit()
        if record.status in ('failed', 'cancelled') or invalid_completed:
            _cleanup_oss_objects(oss_objects)
        return record, False

    except AppError:
        db.session.rollback()
        if reserved:
            _record_failed(record)
            _cleanup_oss_objects(oss_objects)
        raise
    except Exception as exc:
        db.session.rollback()
        if reserved:
            _record_failed(record)
            _cleanup_oss_objects(oss_objects)
        current_app.logger.exception('Failed to create compliance report')
        raise AppError('INTERNAL_ERROR', '报告任务创建失败，请稍后重试', 500) from exc
    finally:
        _cleanup_tmp_files(tmp_paths)


def _record_failed(record):
    """Mark a record as failed (best-effort)."""
    try:
        record.status = 'failed'
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Failed to mark compliance report %s as failed',
            getattr(record, 'id', None),
        )


def _cleanup_oss_objects(object_names):
    """Best-effort deletion of uploaded OSS objects on failure."""
    for name in (object_names or []):
        try:
            delete_object(name)
        except Exception:
            current_app.logger.exception(
                'Failed to delete temporary report OSS object %s', name
            )


def serialize_report_metadata(record):
    """Serialize report metadata shared by create/list/detail responses."""
    biz_params = {}
    if record.param and isinstance(record.param, dict):
        candidate = record.param.get('biz_params', {})
        if isinstance(candidate, dict):
            biz_params = candidate

    documents = biz_params.get('documents', [])
    if not isinstance(documents, list):
        documents = []

    query_input = None
    if record.param and isinstance(record.param, dict):
        query_input = record.param.get('input')

    return {
        'id': record.id,
        'query': query_input,
        'idempotency_key': record.idempotency_key,
        'company_name': biz_params.get('company_name'),
        'industry': biz_params.get('industry'),
        'country': record.country,
        'company_size': record.company_size,
        'budget_range': record.budget_range,
        'business_model': record.business_model,
        'doc_count': len(documents),
        'status': record.status,
        'deleted': bool(record.deleted),
        'created_at': record.created_at.isoformat() if record.created_at else None,
    }


def _extract_result_text(record):
    """Extract result_text from a completed diagnosis record."""
    if record.status != 'completed':
        return None
    result_row = db.session.get(DiagnosisResult, record.id)
    if not result_row or not result_row.result:
        return None
    result_data = result_row.result
    try:
        output = result_data.get('output', [])
        for item in reversed(output):
            if item.get('type') != 'message':
                continue
            for content in item.get('content', []):
                if content.get('type') == 'output_text' and content.get('text') is not None:
                    return content['text']
    except (AttributeError, IndexError, KeyError, TypeError):
        pass
    return None


# -- User-facing functions (own records only, non-deleted) --


def list_reports(user, page=1, per_page=20):
    """List the current user's non-deleted reports with pagination."""
    query = DiagnosisRecord.query.filter(
        DiagnosisRecord.user_id == user.id,
        DiagnosisRecord.deleted.is_(False),
    )
    total = query.count()
    records = (
        query
        .order_by(desc(DiagnosisRecord.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        'reports': [serialize_report_metadata(r) for r in records],
        'meta': {'page': page, 'per_page': per_page, 'total': total},
    }


def get_report_detail(user, report_id):
    """Get a single diagnosis report — must be owned by the user and not deleted."""
    record = db.session.get(DiagnosisRecord, report_id)
    if not record or record.user_id != user.id or record.deleted:
        raise NotFoundError('报告不存在')
    result = serialize_report_metadata(record)
    result['result_text'] = _extract_result_text(record)
    return result


def delete_report(user, report_id):
    """Soft-delete a report owned by the current user."""
    record = db.session.get(DiagnosisRecord, report_id)
    if not record or record.user_id != user.id:
        raise NotFoundError('报告不存在')
    if not record.deleted:
        record.deleted = True
        db.session.commit()
    return serialize_report_metadata(record)


# -- Admin functions (all records, including deleted) --


def list_all_reports(page=1, per_page=20):
    """List all diagnosis records (including deleted) with pagination."""
    total = DiagnosisRecord.query.count()
    records = (
        DiagnosisRecord.query
        .order_by(desc(DiagnosisRecord.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        'reports': [serialize_report_metadata(r) for r in records],
        'meta': {'page': page, 'per_page': per_page, 'total': total},
    }


def get_any_report(report_id):
    """Get any diagnosis report (including deleted) without ownership check."""
    record = db.session.get(DiagnosisRecord, report_id)
    if not record:
        raise NotFoundError('报告不存在')
    result = serialize_report_metadata(record)
    result['result_text'] = _extract_result_text(record)
    return result


def admin_delete_report(report_id):
    """Soft-delete any report without ownership check."""
    record = db.session.get(DiagnosisRecord, report_id)
    if not record:
        raise NotFoundError('报告不存在')
    if not record.deleted:
        record.deleted = True
        db.session.commit()
    return serialize_report_metadata(record)
