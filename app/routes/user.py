from flask import Blueprint, g, jsonify, request

from app.extensions import limiter
from app.services import user_service
from app.utils.auth_utils import jwt_required
from app.utils.errors import AppError


user_bp = Blueprint('user', __name__)


def _email_limit_key():
    """Rate-limit key: authenticated user ID."""
    return str(getattr(g, 'current_user', None).id if hasattr(g, 'current_user') and g.current_user else 'anon')


email_action_limit = limiter.shared_limit(
    '5 per hour',
    scope='email-verification-actions',
    key_func=_email_limit_key,
)


@user_bp.route('/profile', methods=['GET'])
@jwt_required
def profile():
    try:
        result = user_service.get_profile(g.current_user)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@user_bp.route('/email', methods=['PUT'])
@jwt_required
@email_action_limit
def change_email():
    """Bind or replace the current user's email."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': '请求体必须是非空 JSON 对象'}}), 400
    try:
        result = user_service.change_email(
            user=g.current_user,
            new_email=data.get('email', ''),
            password=data.get('password', ''),
        )
        msg = '邮箱已更新，请验证新邮箱' if result.get('verification_email_sent') else '邮箱已更新，但验证邮件发送失败'
        return jsonify({'success': True, 'data': result, 'message': msg}), 200
    except AppError as e:
        return e.to_response()


@user_bp.route('/email/resend-verification', methods=['POST'])
@jwt_required
@email_action_limit
def resend_verification():
    """Resend the verification email for the current user."""
    try:
        result = user_service.resend_verification(g.current_user)
        return jsonify({'success': True, 'data': result, 'message': '验证邮件已发送'}), 200
    except AppError as e:
        return e.to_response()
