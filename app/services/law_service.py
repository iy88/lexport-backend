from datetime import date
import os
import unicodedata
import uuid

from flask import current_app
from sqlalchemy import or_
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from app.extensions import db
from app.models.country import Country
from app.models.draft import LawDraft
from app.models.law import ComplianceScene, Law
from app.utils.errors import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.utils.oss_utils import (
    copy_object,
    delete_object,
    download_file,
    head_object,
    object_exists,
    upload_file,
)
from app.utils.validators import normalize_model_strings


# ---------------------------------------------------------------------------
# Object name generation
# ---------------------------------------------------------------------------

# Control characters and path separators rejected in titles.
_FORBIDDEN_CHARS = set('\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r'
                       '\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19'
                       '\x1a\x1b\x1c\x1d\x1e\x1f\x7f/\\')

MAX_OBJECT_NAME_CHARS = 500
MAX_OBJECT_NAME_BYTES = 1023


def _build_object_name(title_cn, title_en, ext):
    """Build an OSS object name from law titles and file extension.

    Format: ``<title_cn>[-<title_en>]<lowercase-extension>``

    Raises ValidationError (400) for missing extension, illegal characters,
    or names exceeding length limits.
    """
    title_cn = (title_cn or '').strip()
    title_en = (title_en or '').strip()
    ext = (ext or '').strip()

    if not title_cn:
        raise ValidationError('中文标题不能为空')

    if not ext.startswith('.'):
        ext = '.' + ext
    if len(ext) < 2:
        raise ValidationError('文件必须带后缀名')

    for ch in title_cn + title_en + ext:
        if ch in _FORBIDDEN_CHARS:
            raise ValidationError(f'标题或文件后缀包含非法字符: {repr(ch)}')

    # NFC normalise so that composed characters are stored consistently.
    title_cn = unicodedata.normalize('NFC', title_cn)
    title_en = unicodedata.normalize('NFC', title_en)

    ext_lower = ext.lower()

    if title_en:
        name = f'{title_cn}-{title_en}{ext_lower}'
    else:
        name = f'{title_cn}{ext_lower}'

    if len(name) > MAX_OBJECT_NAME_CHARS:
        raise ValidationError(
            f'文件名称过长（{len(name)} 字符，上限 {MAX_OBJECT_NAME_CHARS}）')
    if len(name.encode('utf-8')) > MAX_OBJECT_NAME_BYTES:
        raise ValidationError(
            f'文件名称 UTF-8 字节数超限（上限 {MAX_OBJECT_NAME_BYTES}）')

    return name


# ---------------------------------------------------------------------------
# Tmp-file helpers (UPLOAD_PATH/tmp/laws/)
# ---------------------------------------------------------------------------

def _tmp_dir():
    """Ensure and return the tmp/laws directory path."""
    path = os.path.join(current_app.config['UPLOAD_PATH'], 'tmp', 'laws')
    os.makedirs(path, exist_ok=True)
    return path


def _save_tmp_law_file(file_storage):
    """Save an uploaded file to the tmp/laws directory.

    Returns ``(local_path, original_name, pending_file_name)`` where
    *pending_file_name* is ``<uuid><lowercase-ext>``.
    """
    ext = os.path.splitext(file_storage.filename or '')[1]
    if not ext:
        raise ValidationError('文件必须带后缀名')
    pending_name = str(uuid.uuid4()) + ext.lower()
    local_path = os.path.join(_tmp_dir(), pending_name)

    try:
        file_storage.stream.seek(0)
    except (AttributeError, OSError):
        pass
    file_storage.save(local_path)

    return local_path, (file_storage.filename or ''), pending_name


def _remove_tmp_file(pending_file_name):
    """Delete a single tmp file, ignoring errors."""
    if not pending_file_name:
        return
    try:
        path = os.path.join(_tmp_dir(), pending_file_name)
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _remove_local_path(path):
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _ensure_object_name_available(object_name, law_id=None):
    """Reject object names owned by another DB row or OSS object."""
    query = Law.query.filter(Law.object_name == object_name)
    if law_id is not None:
        query = query.filter(Law.id != law_id)
    # Under InnoDB's default REPEATABLE READ this locks the unique-index gap as
    # well as an existing row, serialising concurrent creates for the same key.
    if query.with_for_update().first():
        raise ConflictError('同名法规文件已存在')
    if object_exists(object_name, bucket_name='LAW_OSS_BUCKET_NAME'):
        raise ConflictError('同名法规文件已存在')


def _prepare_oss_transition(old_name, new_name, new_local_path=None):
    """Write a new official object while retaining enough state to roll back.

    ``new_local_path`` means file replacement.  When it is absent the operation
    is a name-only copy.  The old object is downloaded before any destructive
    action, including same-key overwrites.
    """
    state = {
        'old_name': old_name,
        'new_name': new_name,
        'backup_path': None,
        'target_written': False,
    }

    try:
        if old_name:
            ext = os.path.splitext(old_name)[1]
            state['backup_path'] = os.path.join(
                _tmp_dir(), f'_rollback_{uuid.uuid4().hex}{ext}',
            )
            download_file(
                old_name, state['backup_path'],
                bucket_name='LAW_OSS_BUCKET_NAME',
            )

        if new_local_path:
            upload_file(
                new_local_path, new_name,
                bucket_name='LAW_OSS_BUCKET_NAME',
            )
        elif old_name and new_name != old_name:
            copy_object(
                old_name, new_name,
                bucket_name='LAW_OSS_BUCKET_NAME',
            )
        else:
            return state

        state['target_written'] = True
        if old_name and new_name != old_name:
            delete_object(old_name, bucket_name='LAW_OSS_BUCKET_NAME')
        return state
    except Exception:
        _compensate_oss_transition(state)
        _cleanup_oss_transition(state)
        raise


def _compensate_oss_transition(state):
    """Best-effort restoration for a prepared OSS transition."""
    if not state:
        return
    old_name = state.get('old_name')
    new_name = state.get('new_name')
    backup_path = state.get('backup_path')

    if old_name and backup_path and os.path.isfile(backup_path):
        try:
            upload_file(
                backup_path, old_name,
                bucket_name='LAW_OSS_BUCKET_NAME',
            )
        except Exception as exc:
            current_app.logger.critical(
                'Failed to restore law OSS object %s: %s', old_name, exc,
            )

    if state.get('target_written') and new_name and new_name != old_name:
        try:
            delete_object(new_name, bucket_name='LAW_OSS_BUCKET_NAME')
        except Exception as exc:
            current_app.logger.critical(
                'Failed to remove compensated law OSS object %s: %s',
                new_name, exc,
            )


def _cleanup_oss_transition(state):
    if state:
        _remove_local_path(state.get('backup_path'))


# ---------------------------------------------------------------------------
# Row locking
# ---------------------------------------------------------------------------

def _lock_law(law_id):
    """Acquire a pessimistic row lock on a Law row.

    Returns the Law instance or raises NotFoundError.
    """
    law = (
        Law.query
        .filter(Law.id == law_id)
        .with_for_update()
        .first()
    )
    if not law:
        raise NotFoundError('法规不存在')
    return law


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_law(law, draft=None):
    """Serialize a Law row for the admin API response.

    *draft* is an optional LawDraft instance whose *data* is merged on top.
    """
    base = {
        'id': law.id,
        'title_cn': law.title_cn,
        'title_en': law.title_en,
        'law_number': law.law_number,
        'country_id': law.country_id,
        'scene_id': law.scene_id,
        'effective_date': law.effective_date.isoformat() if law.effective_date else None,
        'summary': law.summary,
        'status': law.status,
        'object_name': law.object_name,
        'has_file': bool(law.object_name or law.pending_file_name),
        'has_draft': draft is not None,
        'review_status': 'pending' if (draft or law.status == 'draft') else 'none',
        'has_pending_file': bool(
            (draft and draft.pending_file_name) or
            (not draft and law.status == 'draft' and law.pending_file_name)
        ),
        'pending_object_name': None,
        'created_at': law.created_at.isoformat() if law.created_at else None,
        'updated_at': law.updated_at.isoformat() if law.updated_at else None,
    }

    # Compute the object name that approval would create.  This also covers a
    # name-only draft where the file remains the current official OSS object.
    pending_file = None
    pending_title_cn = None
    pending_title_en = None

    if draft and draft.pending_file_name:
        pending_file = draft.pending_file_name
        pending_title_cn = draft.data.get('title_cn') if draft.data else None
        pending_title_en = draft.data.get('title_en') if draft.data else None
    elif not draft and law.status == 'draft' and law.pending_file_name:
        pending_file = law.pending_file_name
        pending_title_cn = law.title_cn
        pending_title_en = law.title_en

    if draft and not pending_file and law.object_name:
        pending_file = law.object_name
        pending_title_cn = (draft.data or {}).get('title_cn', law.title_cn)
        pending_title_en = (draft.data or {}).get('title_en', law.title_en)

    if pending_file and pending_title_cn:
        ext = os.path.splitext(pending_file)[1]
        try:
            base['pending_object_name'] = _build_object_name(
                pending_title_cn, pending_title_en or '', ext,
            )
        except ValidationError:
            base['pending_object_name'] = None

    # Merge draft data on top (for preview).
    if draft and draft.data:
        for key, value in draft.data.items():
            if key in base and key not in ('id', 'created_at', 'updated_at',
                                            'object_name', 'has_file', 'has_draft',
                                            'review_status', 'has_pending_file',
                                            'pending_object_name'):
                base[key] = value
        # When draft data is merged, the draft's own file state takes precedence.
        if draft.pending_file_name:
            base['has_file'] = True
            base['has_pending_file'] = True

    return base


# ---------------------------------------------------------------------------
# Form parsing (multipart or JSON)
# ---------------------------------------------------------------------------

LAW_FORM_FIELDS = [
    'title_cn', 'title_en', 'law_number', 'country_id', 'scene_id',
    'effective_date', 'summary',
]


def _validate_law_data(data, partial=False):
    """Normalize and validate Law business fields before DB or OSS work."""
    if not isinstance(data, dict):
        raise ValidationError('法规数据必须为对象')
    unknown = set(data) - set(LAW_FORM_FIELDS)
    if unknown:
        raise ValidationError(f'不支持的字段: {", ".join(sorted(unknown))}')

    values = normalize_model_strings(
        Law,
        {key: value for key, value in data.items() if key in LAW_FORM_FIELDS},
        required=('title_cn', 'country_id', 'scene_id'),
    )
    if not partial:
        for field in ('title_cn', 'country_id', 'scene_id'):
            if values.get(field) in (None, ''):
                raise ValidationError(f'{field} 不能为空')

    if 'effective_date' in values:
        value = values['effective_date']
        if value in (None, ''):
            values['effective_date'] = None
        elif isinstance(value, date):
            values['effective_date'] = value
        elif isinstance(value, str):
            try:
                values['effective_date'] = date.fromisoformat(value.strip())
            except ValueError as exc:
                raise ValidationError(
                    'effective_date 必须为有效的 YYYY-MM-DD 日期',
                ) from exc
        else:
            raise ValidationError('effective_date 必须为 YYYY-MM-DD')

    if 'country_id' in values and not db.session.get(
            Country, values['country_id']):
        raise ValidationError('country_id 不存在')
    if 'scene_id' in values and not db.session.get(
            ComplianceScene, values['scene_id']):
        raise ValidationError('scene_id 不存在')
    return values


def _law_json_values(values):
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in values.items()
    }


def _convert_law_write_error(exc):
    """Convert user-caused persistence failures while preserving OSS cleanup."""
    if isinstance(exc, IntegrityError):
        raise ValidationError('法规数据引用无效或与现有记录冲突') from exc
    if isinstance(exc, (DataError, StatementError)):
        raise ValidationError('法规字段类型或长度不合法') from exc


def _parse_law_form(form):
    """Extract law text fields from a dict-like *form* (request.form or JSON)."""
    data = {}
    for key in LAW_FORM_FIELDS:
        value = form.get(key)
        if value is not None:
            data[key] = value
    return data


# ---------------------------------------------------------------------------
# Reference data for admin list meta
# ---------------------------------------------------------------------------

def _law_ref_data():
    return {
        'countries': [
            {'id': c.id, 'name_zh': c.name_zh}
            for c in Country.query.order_by(Country.sort_order).all()
        ],
        'scenes': [
            {'id': s.id, 'label_zh': s.label_zh}
            for s in ComplianceScene.query.order_by(ComplianceScene.sort_order).all()
        ],
    }


# ---------------------------------------------------------------------------
# Admin list / detail
# ---------------------------------------------------------------------------

def list_laws(page=1, per_page=20, status=None, review_status=None, filters=None):
    """Admin law list with optional *status* and *review_status* filters.

    - *status* filters ``Law.status`` (draft / published / None=all).
    - *review_status* filters presence of a LawDraft row:
      ``pending`` → has draft, ``none`` → no draft.
    """
    if status not in (None, 'draft', 'published'):
        raise ValidationError('status 必须为 draft 或 published')
    if review_status not in (None, 'pending', 'none'):
        raise ValidationError('review_status 必须为 pending 或 none')

    query = Law.query

    if status:
        query = query.filter(Law.status == status)

    draft_ids = db.session.query(LawDraft.law_id)
    if review_status == 'pending':
        query = query.filter(or_(Law.status == 'draft', Law.id.in_(draft_ids)))
    elif review_status == 'none':
        query = query.filter(Law.status == 'published', Law.id.notin_(draft_ids))

    if filters:
        keyword = filters.get('keyword')
        if keyword:
            query = query.filter(or_(
                Law.title_cn.contains(keyword),
                Law.title_en.contains(keyword),
                Law.law_number.contains(keyword),
            ))
        if filters.get('country_id'):
            query = query.filter(Law.country_id == filters['country_id'])
        if filters.get('scene_id'):
            query = query.filter(Law.scene_id == filters['scene_id'])

    query = query.order_by(Law.id.desc())
    total = query.count()
    laws = query.offset((page - 1) * per_page).limit(per_page).all()

    # Batch-load drafts so we can tag review_status efficiently.
    law_ids = [l.id for l in laws]
    draft_map = {}
    if law_ids:
        drafts = LawDraft.query.filter(LawDraft.law_id.in_(law_ids)).all()
        draft_map = {d.law_id: d for d in drafts}

    return {
        'items': [_serialize_law(l, draft_map.get(l.id)) for l in laws],
        'meta': {
            'page': page, 'per_page': per_page, 'total': total,
            **_law_ref_data(),
        },
    }


def get_law_with_draft(law_id):
    """Admin law detail with draft preview merged in."""
    law = db.session.get(Law, law_id)
    if not law:
        raise NotFoundError('法规不存在')
    draft = LawDraft.query.filter_by(law_id=law_id).first()
    return {'item': _serialize_law(law, draft)}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_law(data, file_storage, user):
    """Create a Law record.

    - **admin without file** → published, object_name=NULL.
    - **admin with file**    → upload to OSS, published with object_name.
    - **editor**             → draft; file goes to tmp as pending_file_name.
    """
    if user.role not in ('admin', 'editor'):
        raise AuthenticationError('权限不足', http_status=403)
    data = _validate_law_data(data, partial=False)
    is_admin = user.role == 'admin'
    status = 'published' if is_admin else 'draft'
    pending_file_name = None
    object_name = None
    tmp_path = None
    uploaded_to_oss = False
    committed = False

    try:
        if file_storage and file_storage.filename:
            tmp_path, original_name, pending_file_name = _save_tmp_law_file(file_storage)
            ext = os.path.splitext(original_name)[1]
            object_name = _build_object_name(
                data.get('title_cn', ''),
                data.get('title_en', ''),
                ext,
            )

            if is_admin:
                _ensure_object_name_available(object_name)
                upload_file(tmp_path, object_name, bucket_name='LAW_OSS_BUCKET_NAME')
                uploaded_to_oss = True

        law = Law(
            title_cn=data['title_cn'],
            title_en=data.get('title_en') or None,
            law_number=data.get('law_number') or None,
            country_id=data['country_id'],
            scene_id=data['scene_id'],
            effective_date=data.get('effective_date') or None,
            summary=data.get('summary') or None,
            object_name=object_name if is_admin else None,
            pending_file_name=None if is_admin else pending_file_name,
            status=status,
        )
        db.session.add(law)
        db.session.commit()
        committed = True
        return {'item': _serialize_law(law)}

    except Exception as exc:
        db.session.rollback()
        # Rollback OSS: delete uploaded object when DB commit fails.
        if uploaded_to_oss and not committed and object_name:
            try:
                # A concurrent create may have won the unique DB key after both
                # requests passed the OSS preflight.  Never delete an object now
                # owned by that committed row.
                owner = Law.query.filter(Law.object_name == object_name).first()
                if not owner:
                    delete_object(object_name, bucket_name='LAW_OSS_BUCKET_NAME')
            except Exception:
                pass
        _convert_law_write_error(exc)
        raise
    finally:
        # Admin uploads are transient.  Editor uploads must remain available for
        # later approval after a successful draft commit.
        if tmp_path and (is_admin or not committed):
            _remove_tmp_file(pending_file_name)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def update_law(law_id, data, file_storage, user):
    """Update a Law, handling file uploads and the draft workflow.

    See docs/law-oss-plan.md §3 for the full decision matrix.
    """
    if user.role not in ('admin', 'editor'):
        raise AuthenticationError('权限不足', http_status=403)
    data = _validate_law_data(data, partial=True)
    is_admin = user.role == 'admin'
    law = _lock_law(law_id)
    existing_draft = LawDraft.query.filter_by(law_id=law_id).first()

    if is_admin and law.status == 'published' and existing_draft:
        raise ConflictError('法规有待审核修改，请先审核或丢弃草稿')

    if is_admin and law.status == 'published':
        return _admin_update_published(law, data, file_storage)
    elif is_admin and law.status == 'draft':
        return _admin_update_draft(law, data, file_storage)
    elif not is_admin and law.status == 'published':
        return _editor_update_published(law, data, file_storage, user)
    else:  # editor on own draft
        return _editor_update_draft(law, data, file_storage)


def _admin_update_published(law, data, file_storage):
    """Admin updating a published law directly."""
    has_file_change = bool(file_storage and file_storage.filename)
    has_name_change = (
        'title_cn' in data and data['title_cn'] != law.title_cn
    ) or (
        'title_en' in data and
        (data.get('title_en') or '') != (law.title_en or '')
    )

    new_object_name = None
    old_object_name = law.object_name
    tmp_path = None
    pending_name = None
    transition = None

    try:
        # --- file change: compute new object name ---
        if has_file_change:
            tmp_path, original_name, pending_name = _save_tmp_law_file(file_storage)
            ext = os.path.splitext(original_name)[1]
            # Use new title if provided, else current.
            cn = data.get('title_cn', law.title_cn)
            en = data.get('title_en', law.title_en or '')
            new_object_name = _build_object_name(cn, en, ext)

        elif has_name_change and old_object_name:
            # Name-only change: compute new object name from current ext.
            ext = os.path.splitext(old_object_name)[1]
            cn = data.get('title_cn', law.title_cn)
            en = data.get('title_en', law.title_en or '')
            new_object_name = _build_object_name(cn, en, ext)

        # Check for name conflict (unless target is this law's own current name).
        if new_object_name and new_object_name != old_object_name:
            _ensure_object_name_available(new_object_name, law.id)

        # --- OSS operations ---
        if has_file_change:
            transition = _prepare_oss_transition(
                old_object_name, new_object_name, tmp_path,
            )
        elif has_name_change and old_object_name and new_object_name != old_object_name:
            transition = _prepare_oss_transition(
                old_object_name, new_object_name,
            )

        # --- DB update ---
        for key, value in data.items():
            if key in LAW_FORM_FIELDS and hasattr(law, key):
                setattr(law, key, value)
        if new_object_name is not None:
            law.object_name = new_object_name
        if has_file_change:
            law.pending_file_name = None
        law.status = 'published'
        db.session.commit()
        _cleanup_oss_transition(transition)
        transition = None
        return {'item': _serialize_law(law)}

    except Exception as exc:
        db.session.rollback()
        _compensate_oss_transition(transition)
        _convert_law_write_error(exc)
        raise
    finally:
        if tmp_path:
            _remove_tmp_file(pending_name)
        _cleanup_oss_transition(transition)


def _admin_update_draft(law, data, file_storage):
    """Admin updating a draft law — direct update, no OSS, no publish."""
    old_pending = law.pending_file_name
    new_pending = None
    try:
        if file_storage and file_storage.filename:
            _, _, new_pending = _save_tmp_law_file(file_storage)
            law.pending_file_name = new_pending

        for key, value in data.items():
            if key in LAW_FORM_FIELDS and hasattr(law, key):
                setattr(law, key, value)
        db.session.commit()
        if new_pending and old_pending:
            _remove_tmp_file(old_pending)
        return {'item': _serialize_law(law)}
    except Exception as exc:
        db.session.rollback()
        if new_pending:
            _remove_tmp_file(new_pending)
        _convert_law_write_error(exc)
        raise


def _editor_update_published(law, data, file_storage, user):
    """Editor modifying a published law → write to LawDraft table."""
    draft = LawDraft.query.filter_by(law_id=law.id).first()
    # Preserve earlier editor changes when a draft is updated incrementally.
    full = dict(draft.data) if draft and draft.data else {
        'title_cn': law.title_cn,
        'title_en': law.title_en,
        'law_number': law.law_number,
        'country_id': law.country_id,
        'scene_id': law.scene_id,
        'effective_date': law.effective_date.isoformat() if law.effective_date else None,
        'summary': law.summary,
    }
    full.update(_law_json_values({
        k: v for k, v in data.items() if k in LAW_FORM_FIELDS
    }))

    if not draft:
        draft = LawDraft(law_id=law.id, data=full, editor_id=user.id)
        db.session.add(draft)
    else:
        draft.data = full
        draft.editor_id = user.id

    old_pending = draft.pending_file_name
    new_pending = None
    try:
        if file_storage and file_storage.filename:
            _, _, new_pending = _save_tmp_law_file(file_storage)
            draft.pending_file_name = new_pending

        db.session.commit()
        if new_pending and old_pending:
            _remove_tmp_file(old_pending)
        return {'item': _serialize_law(law, draft)}
    except Exception as exc:
        db.session.rollback()
        if new_pending:
            _remove_tmp_file(new_pending)
        _convert_law_write_error(exc)
        raise


def _editor_update_draft(law, data, file_storage):
    """Editor updating their own draft — direct update of Law row."""
    old_pending = law.pending_file_name
    new_pending = None
    try:
        if file_storage and file_storage.filename:
            _, _, new_pending = _save_tmp_law_file(file_storage)
            law.pending_file_name = new_pending

        for key, value in data.items():
            if key in LAW_FORM_FIELDS and hasattr(law, key):
                setattr(law, key, value)
        law.status = 'draft'
        db.session.commit()
        if new_pending and old_pending:
            _remove_tmp_file(old_pending)
        return {'item': _serialize_law(law)}
    except Exception as exc:
        db.session.rollback()
        if new_pending:
            _remove_tmp_file(new_pending)
        _convert_law_write_error(exc)
        raise


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

def approve_law(law_id):
    """Publish a main-table draft or approve changes to a published law."""
    law = _lock_law(law_id)
    draft = LawDraft.query.filter_by(law_id=law_id).first()

    if not draft and law.status != 'draft':
        raise AppError('VALIDATION_ERROR', '该法规没有待审核修改', 400)

    target_data = {
        'title_cn': law.title_cn,
        'title_en': law.title_en,
        'law_number': law.law_number,
        'country_id': law.country_id,
        'scene_id': law.scene_id,
        'effective_date': law.effective_date,
        'summary': law.summary,
    }
    if draft and draft.data:
        if not isinstance(draft.data, dict):
            raise ValidationError('法规草稿数据格式无效')
        target_data.update(draft.data)
    target_values = _validate_law_data(target_data, partial=False)

    new_object_name = None
    old_object_name = law.object_name
    pending_tmp = draft.pending_file_name if draft else law.pending_file_name
    transition = None

    try:
        # Compute target object name if there's a pending file or name change.
        if pending_tmp:
            ext = os.path.splitext(pending_tmp)[1]
            cn = target_values['title_cn']
            en = target_values.get('title_en') or ''
            new_object_name = _build_object_name(cn, en, ext)
        elif draft and draft.data:
            # Possible name-only change with existing OSS object.
            cn_draft = target_values['title_cn']
            en_draft = target_values.get('title_en') or ''
            if cn_draft != law.title_cn or en_draft != (law.title_en or ''):
                if old_object_name:
                    ext = os.path.splitext(old_object_name)[1]
                    new_object_name = _build_object_name(cn_draft, en_draft, ext)

        # Check for name conflict.
        if new_object_name and new_object_name != old_object_name:
            _ensure_object_name_available(new_object_name, law.id)

        # --- OSS operations ---
        if pending_tmp and new_object_name:
            tmp_path = os.path.join(_tmp_dir(), pending_tmp)
            if not os.path.isfile(tmp_path):
                raise AppError('OSS_ERROR', '待审文件丢失，请重新上传', 502)
            transition = _prepare_oss_transition(
                old_object_name, new_object_name, tmp_path,
            )

        elif new_object_name and new_object_name != old_object_name:
            # Name change, no new file → copy + delete old.
            transition = _prepare_oss_transition(
                old_object_name, new_object_name,
            )

        # --- DB update ---
        for key, value in target_values.items():
            setattr(law, key, value)
        if new_object_name:
            law.object_name = new_object_name
        law.pending_file_name = None
        law.status = 'published'
        if draft:
            db.session.delete(draft)
        db.session.commit()

        # Clean up pending tmp file after successful commit.
        if pending_tmp:
            _remove_tmp_file(pending_tmp)
        _cleanup_oss_transition(transition)
        transition = None

        return {'item': _serialize_law(law)}

    except Exception as exc:
        db.session.rollback()
        _compensate_oss_transition(transition)
        _convert_law_write_error(exc)
        raise
    finally:
        _cleanup_oss_transition(transition)


# ---------------------------------------------------------------------------
# Batch approve (per-item, independent transactions)
# ---------------------------------------------------------------------------

def batch_approve_laws(ids):
    """Approve each law independently; one failure does not roll back others."""
    approved = []
    failed = []
    for lid in ids:
        try:
            approve_law(lid)
            approved.append(lid)
        except AppError as exc:
            failed.append({
                'id': lid,
                'code': exc.code if hasattr(exc, 'code') else 'UNKNOWN',
                'message': getattr(exc, 'message', str(exc)),
            })
    return {'approved': approved, 'failed': failed}


# ---------------------------------------------------------------------------
# Suspend
# ---------------------------------------------------------------------------

def suspend_law(law_id):
    """Set a published law back to draft, moving OSS object to tmp.

    - Discards any existing LawDraft + its pending file.
    - Downloads OSS object → tmp, deletes OSS object.
    - Sets object_name=NULL, pending_file_name=<uuid>, status=draft.
    """
    law = _lock_law(law_id)
    if law.status != 'published':
        raise AppError('VALIDATION_ERROR', '仅已发布法规可以挂起', 400)
    draft = LawDraft.query.filter_by(law_id=law_id).first()

    old_pending = None
    if draft:
        old_pending = draft.pending_file_name
        db.session.delete(draft)

    old_object_name = law.object_name
    new_pending = None
    committed = False

    try:
        if old_object_name:
            ext = os.path.splitext(old_object_name)[1]
            new_pending = str(uuid.uuid4()) + ext.lower()
            local_path = os.path.join(_tmp_dir(), new_pending)
            download_file(old_object_name, local_path, bucket_name='LAW_OSS_BUCKET_NAME')
            delete_object(old_object_name, bucket_name='LAW_OSS_BUCKET_NAME')

        law.object_name = None
        law.pending_file_name = new_pending
        law.status = 'draft'
        db.session.commit()
        committed = True

        if old_pending:
            _remove_tmp_file(old_pending)

        return {'item': _serialize_law(law)}

    except Exception:
        db.session.rollback()
        # Attempt to restore OSS object from local copy.
        if not committed and new_pending and old_object_name:
            local_path = os.path.join(_tmp_dir(), new_pending)
            if os.path.isfile(local_path):
                try:
                    upload_file(local_path, old_object_name, bucket_name='LAW_OSS_BUCKET_NAME')
                except Exception:
                    pass
        if not committed and new_pending:
            _remove_tmp_file(new_pending)
        raise


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_law(law_id, user=None):
    """Delete a Law.

    - **draft**: delete DB record + local tmp file.
    - **published**: download rollback, delete OSS, delete DB.  DB failure →
      re-upload to restore OSS.
    """
    law = _lock_law(law_id)
    if user is not None and user.role != 'admin' and law.status != 'draft':
        raise AppError('AUTH_ERROR', '仅可删除草稿', 403)

    old_object_name = law.object_name
    pending = law.pending_file_name
    draft = LawDraft.query.filter_by(law_id=law_id).first()
    draft_pending = draft.pending_file_name if draft else None

    if law.status == 'draft':
        db.session.delete(law)
        if draft:
            db.session.delete(draft)
        db.session.commit()
        _remove_tmp_file(pending)
        if draft_pending:
            _remove_tmp_file(draft_pending)
        return

    # Published: download rollback before deleting.
    rollback_local = None
    try:
        if old_object_name:
            ext = os.path.splitext(old_object_name)[1]
            rb_name = f'_delete_rollback_{uuid.uuid4().hex}{ext}'
            rollback_local = os.path.join(_tmp_dir(), rb_name)
            download_file(old_object_name, rollback_local, bucket_name='LAW_OSS_BUCKET_NAME')
            delete_object(old_object_name, bucket_name='LAW_OSS_BUCKET_NAME')

        db.session.delete(law)
        if draft:
            db.session.delete(draft)
        db.session.commit()

        if draft_pending:
            _remove_tmp_file(draft_pending)

    except Exception:
        db.session.rollback()
        if rollback_local and old_object_name and os.path.isfile(rollback_local):
            try:
                upload_file(rollback_local, old_object_name, bucket_name='LAW_OSS_BUCKET_NAME')
            except Exception:
                pass
        raise
    finally:
        if rollback_local:
            try:
                os.remove(rollback_local)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Discard draft (admin only)
# ---------------------------------------------------------------------------

def discard_law_draft(law_id):
    """Discard a pending LawDraft and its tmp file, keeping the published law."""
    law = _lock_law(law_id)

    draft = LawDraft.query.filter_by(law_id=law_id).first()
    if not draft:
        raise AppError('VALIDATION_ERROR', '该法规没有待审核修改', 400)

    old_pending = draft.pending_file_name
    db.session.delete(draft)
    db.session.commit()

    if old_pending:
        _remove_tmp_file(old_pending)

    return {'item': _serialize_law(law)}


# ---------------------------------------------------------------------------
# Public law helpers (used by public routes)
# ---------------------------------------------------------------------------

def _public_law_dict(law):
    """Serialize a published Law for the public API."""
    return {
        'id': law.id,
        'title_cn': law.title_cn,
        'title_en': law.title_en,
        'law_number': law.law_number,
        'country_id': law.country_id,
        'scene_id': law.scene_id,
        'effective_date': law.effective_date.isoformat() if law.effective_date else None,
        'summary': law.summary,
        'has_file': bool(law.object_name),
        'created_at': law.created_at.isoformat() if law.created_at else None,
    }


def get_laws(page=1, per_page=20, country_id=None, scene_id=None, keyword=None):
    """Public law list — published only."""
    query = Law.query.filter(Law.status == 'published')

    if country_id:
        query = query.filter(Law.country_id == country_id)
    if scene_id:
        query = query.filter(Law.scene_id == scene_id)
    if keyword:
        query = query.filter(or_(
            Law.title_cn.contains(keyword),
            Law.title_en.contains(keyword),
        ))

    total = query.count()

    laws = (
        query
        .order_by(Law.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    countries = Country.query.order_by(Country.sort_order).all()
    scenes = ComplianceScene.query.order_by(ComplianceScene.sort_order).all()

    return {
        'laws': [_public_law_dict(l) for l in laws],
        'meta': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in countries],
            'scenes': [{'id': s.id, 'label_zh': s.label_zh} for s in scenes],
        },
    }


def get_law_detail(law_id):
    """Public law detail — published only."""
    law = Law.query.filter_by(id=law_id, status='published').first()
    if not law:
        raise NotFoundError('法规不存在')
    return _public_law_dict(law)
