from flask import Blueprint, request, jsonify

from app.extensions import limiter
from app.services import auth_service
from app.utils.errors import AppError

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
@limiter.limit('5 per hour')
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': '请求体必须是非空 JSON 对象'}}), 400

    try:
        result = auth_service.register(
            username=data.get('username', ''),
            password=data.get('password', ''),
            email=data.get('email', ''),
        )
        msg = '注册成功，请验证邮箱' if result.get('verification_email_sent') else '账号已创建，但验证邮件发送失败，请登录后重试'
        return jsonify({'success': True, 'data': result, 'message': msg}), 201
    except AppError as e:
        return e.to_response()


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': '请求体必须是非空 JSON 对象'}}), 400

    try:
        result = auth_service.login(
            login_id=data.get('login_id', ''),
            password=data.get('password', ''),
        )
        return jsonify({'success': True, 'data': result, 'message': '登录成功'}), 200
    except AppError as e:
        return e.to_response()


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email_route():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'success': False, 'error': {'code': 'VALIDATION_ERROR', 'message': '请求体必须是非空 JSON 对象'}}), 400
    token = data.get('token', '')

    try:
        auth_service.verify_email(token)
        return jsonify({'success': True, 'data': None, 'message': '邮箱验证成功'}), 200
    except AppError as e:
        return e.to_response()
