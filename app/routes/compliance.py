import uuid

from flask import Blueprint, g, jsonify, request

from app.extensions import limiter
from app.services import compliance_service
from app.utils.auth_utils import jwt_required
from app.utils.errors import AppError, ValidationError

compliance_bp = Blueprint('compliance', __name__)


def _report_limit_key():
    """Rate-limit key: user ID for non-admin, None for admin (exempt)."""
    user = getattr(g, 'current_user', None)
    if user and user.role == 'admin':
        return None
    return str(user.id) if user else 'anon'


@compliance_bp.route('', methods=['POST'])
@jwt_required
@limiter.limit('5 per minute', key_func=_report_limit_key,
               exempt_when=lambda: _report_limit_key() is None)
def create_report():
    """Create a compliance report generation task."""
    try:
        # Idempotency key
        idem_key = request.headers.get('Idempotency-Key', '').strip()
        if not idem_key:
            raise ValidationError('缺少 Idempotency-Key 请求头')
        try:
            parsed_key = uuid.UUID(idem_key)
        except (ValueError, AttributeError):
            raise ValidationError('Idempotency-Key 必须为有效的 UUID')

        if str(parsed_key) != idem_key:
            raise ValidationError('Idempotency-Key 必须为规范的小写 UUID 字符串')

        record, replayed = compliance_service.create_report(
            user=g.current_user,
            form=request.form,
            files=request.files,
            idempotency_key=idem_key,
        )
        terminal = record.status in ('completed', 'failed', 'cancelled')
        status_code = 200 if replayed and terminal else 202
        message = '返回已有报告任务' if replayed else '报告生成任务已创建'
        return jsonify({
            'success': True,
            'data': {
                **compliance_service.serialize_report_metadata(record),
                'task_id': record.task_id,
            },
            'message': message,
        }), status_code
    except AppError as e:
        return e.to_response()


@compliance_bp.route('', methods=['GET'])
@jwt_required
def list_reports():
    """List the current user's own compliance reports."""
    try:
        page = max(1, request.args.get('page', 1, type=int) or 1)
        per_page = min(100, max(1, request.args.get('per_page', 20, type=int) or 20))
        result = compliance_service.list_reports(
            user=g.current_user,
            page=page,
            per_page=per_page,
        )
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@compliance_bp.route('/<int:report_id>', methods=['GET'])
@jwt_required
def get_report(report_id):
    """Get a single compliance report detail (own records only)."""
    try:
        result = compliance_service.get_report_detail(
            user=g.current_user,
            report_id=report_id,
        )
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@compliance_bp.route('/<int:report_id>', methods=['DELETE'])
@jwt_required
def delete_report(report_id):
    """Soft-delete a compliance report (own records only)."""
    try:
        result = compliance_service.delete_report(
            user=g.current_user,
            report_id=report_id,
        )
        return jsonify({'success': True, 'data': result, 'message': '报告已删除'}), 200
    except AppError as e:
        return e.to_response()
