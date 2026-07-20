from flask import Blueprint, request, jsonify, g

from app.services import compliance_service
from app.utils.auth_utils import jwt_required
from app.utils.errors import AppError

compliance_bp = Blueprint('compliance', __name__)


@compliance_bp.route('', methods=['POST'])
@jwt_required
def create_report():
    """Create a compliance report generation task."""
    try:
        record = compliance_service.create_report(
            user=g.current_user,
            form=request.form,
            files=request.files,
        )
        return jsonify({
            'success': True,
            'data': {
                **compliance_service.serialize_report_metadata(record),
                'task_id': record.task_id,
            },
            'message': '报告生成任务已创建',
        }), 202
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
