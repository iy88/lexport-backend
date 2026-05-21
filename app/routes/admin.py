from flask import Blueprint, request, jsonify, g

from app.extensions import db
from app.models.agency import Agency
from app.models.law import Law
from app.models.news import News
from app.models.user import User
from app.services import admin_service
from app.utils.auth_utils import jwt_required
from app.utils.errors import AppError, NotFoundError

admin_bp = Blueprint('admin', __name__)

MODELS = {'laws': Law, 'news': News, 'agencies': Agency}


# -- User management (admin only) --

@admin_bp.route('/users', methods=['GET'])
@jwt_required(role='admin')
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = User.query.order_by(User.id.desc())
    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'success': True,
        'data': {
            'items': [u.to_dict() for u in users],
            'meta': {'page': page, 'per_page': per_page, 'total': total},
        },
        'message': '成功',
    }), 200


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required(role='admin')
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        raise NotFoundError('用户不存在')
    if user.role == 'admin':
        return jsonify({
            'success': False,
            'error': {'code': 'AUTH_ERROR', 'message': '不能修改管理员权限'},
        }), 403
    data = request.get_json(silent=True) or {}
    if 'role' in data:
        if data['role'] not in ('user', 'admin', 'editor'):
            return jsonify({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': '无效的角色值'},
            }), 400
        user.role = data['role']
    db.session.commit()
    return jsonify({
        'success': True,
        'data': {'item': user.to_dict()},
        'message': '更新成功',
    }), 200


def _get_model():
    resource = request.view_args['resource']
    return MODELS[resource]


@admin_bp.route('/<string:resource>', methods=['GET'])
@jwt_required
def list_(resource):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    try:
        result = admin_service.list_items(_get_model(), resource, page, per_page, status=status)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/<string:resource>', methods=['POST'])
@jwt_required
def create(resource):
    data = request.get_json(silent=True) or {}
    try:
        result = admin_service.create_item(_get_model(), data, g.current_user)
        return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201
    except AppError as e:
        return e.to_response()


@admin_bp.route('/<string:resource>/<int:item_id>', methods=['GET'])
@jwt_required
def get(resource, item_id):
    try:
        result = admin_service.get_item(_get_model(), item_id)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/<string:resource>/<int:item_id>', methods=['PUT'])
@jwt_required
def update(resource, item_id):
    data = request.get_json(silent=True) or {}
    try:
        result = admin_service.update_item(_get_model(), item_id, data, g.current_user)
        return jsonify({'success': True, 'data': result, 'message': '更新成功'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/<string:resource>/<int:item_id>', methods=['DELETE'])
@jwt_required(role='admin')
def delete(resource, item_id):
    try:
        admin_service.delete_item(_get_model(), item_id)
        return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/<string:resource>/<int:item_id>/approve', methods=['POST'])
@jwt_required(role='admin')
def approve(resource, item_id):
    try:
        result = admin_service.approve_item(_get_model(), item_id)
        return jsonify({'success': True, 'data': result, 'message': '审核通过'}), 200
    except AppError as e:
        return e.to_response()
