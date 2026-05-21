from flask import Blueprint, jsonify, g

from app.services import user_service
from app.utils.auth_utils import jwt_required
from app.utils.errors import AppError

user_bp = Blueprint('user', __name__)


@user_bp.route('/profile', methods=['GET'])
@jwt_required
def profile():
    try:
        result = user_service.get_profile(g.current_user)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()
