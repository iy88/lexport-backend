import os
import uuid

from flask import Blueprint, current_app, request, jsonify, g

from app.extensions import db
from app.models.agency import Agency, AgencyCategory, AgencyScene
from app.models.budget_range import BudgetRange
from app.models.company_size import CompanySize
from app.models.content import NewsText
from app.models.country import Country
from app.models.draft import LawDraft, NewsDraft, AgencyDraft
from app.models.law import ComplianceScene, Law
from app.models.news import News, NewsTag, NewsTagRelation
from app.models.user import User
from app.services import admin_service
from app.utils.auth_utils import jwt_required
from app.utils.errors import AppError, NotFoundError

admin_bp = Blueprint('admin', __name__)

# Content table models with draft (model, draft_model, fk_field)
CONTENT_MODELS = {'agencies': (Agency, AgencyDraft, 'agency_id')}

# Reference table models (no status, no draft)
REF_MODELS = {
    'countries': Country,
    'compliance-scenes': ComplianceScene,
    'agency-categories': AgencyCategory,
    'agency-scenes': AgencyScene,
    'budget-ranges': BudgetRange,
    'company-sizes': CompanySize,
}

EDITOR_RESTRICTED = {'budget-ranges', 'company-sizes'}


# -- Helpers --

def _save_uploaded_file(file):
    ext = os.path.splitext(file.filename)[1]
    filename = str(uuid.uuid4()) + ext
    upload_dir = os.path.join(current_app.config['UPLOAD_PATH'], 'laws')
    file.save(os.path.join(upload_dir, filename))
    return filename


def _remove_file(filename):
    if not filename:
        return
    try:
        filepath = os.path.join(current_app.config['UPLOAD_PATH'], 'laws', filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass


# ===================== Agencies (content, generic) =====================

@admin_bp.route('/agencies', methods=['GET'])
@jwt_required
def list_agencies():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    filters = {k: request.args.get(k) for k in [
        'scene_id', 'category_id', 'region', 'keyword',
    ] if request.args.get(k)}
    model, _, _ = CONTENT_MODELS['agencies']
    result = admin_service.list_items(model, 'agencies', page, per_page, status, filters)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/agencies/<int:item_id>', methods=['GET'])
@jwt_required
def get_agency(item_id):
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.get_item_with_draft(model, draft_model, item_id, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/agencies', methods=['POST'])
@jwt_required
def create_agency():
    data = request.get_json(silent=True) or {}
    model, _, _ = CONTENT_MODELS['agencies']
    result = admin_service.create_item(model, data, g.current_user)
    return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201


@admin_bp.route('/agencies/<int:item_id>', methods=['PUT'])
@jwt_required
def update_agency(item_id):
    data = request.get_json(silent=True) or {}
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.update_item_with_draft(model, draft_model, item_id, data, g.current_user, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '更新成功'}), 200


@admin_bp.route('/agencies/<int:item_id>', methods=['DELETE'])
@jwt_required
def delete_agency(item_id):
    model, _, _ = CONTENT_MODELS['agencies']
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    if g.current_user.role != 'admin' and item.status != 'draft':
        raise AppError('AUTH_ERROR', '仅可删除草稿', 403)
    admin_service.delete_item(model, item_id)
    return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200


@admin_bp.route('/agencies/<int:item_id>/approve', methods=['POST'])
@jwt_required(role='admin')
def approve_agency(item_id):
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.approve_item(model, draft_model, item_id, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '审核通过'}), 200


@admin_bp.route('/agencies/<int:item_id>/suspend', methods=['POST'])
@jwt_required(role='admin')
def suspend_agency(item_id):
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.suspend_item(model, draft_model, item_id, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '已挂起'}), 200


# ===================== News (dedicated, content + draft) =====================

@admin_bp.route('/news', methods=['GET'])
@jwt_required
def list_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    filters = {k: request.args.get(k) for k in [
        'type', 'country_id', 'date_from', 'date_to', 'keyword',
    ] if request.args.get(k)}
    result = admin_service.list_items(News, 'news', page, per_page, status, filters)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/news/<int:item_id>', methods=['GET'])
@jwt_required
def get_news(item_id):
    result = admin_service.get_item_with_draft(News, NewsDraft, item_id, 'news_id')
    text = NewsText.query.get(item_id)
    result['item']['content'] = text.content if text else None
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/news', methods=['POST'])
@jwt_required
def create_news():
    data = request.get_json(silent=True) or {}
    tag_ids = data.pop('tag_ids', [])
    content = data.pop('content', None)

    result = admin_service.create_item(News, data, g.current_user)
    item_id = result['item']['id']

    if content:
        db.session.add(NewsText(news_id=item_id, content=content))
    for tid in tag_ids:
        db.session.add(NewsTagRelation(news_id=item_id, tag_id=tid))
    db.session.commit()

    return jsonify({'success': True, 'data': _news_detail(item_id), 'message': '创建成功'}), 201


@admin_bp.route('/news/<int:item_id>', methods=['PUT'])
@jwt_required
def update_news(item_id):
    data = request.get_json(silent=True) or {}
    tag_ids = data.pop('tag_ids', None)
    content = data.pop('content', None)

    result = admin_service.update_item_with_draft(News, NewsDraft, item_id, data, g.current_user, 'news_id')

    if content is not None:
        text = NewsText.query.get(item_id)
        if text:
            text.content = content
        else:
            db.session.add(NewsText(news_id=item_id, content=content))
        db.session.commit()

    if tag_ids is not None:
        NewsTagRelation.query.filter_by(news_id=item_id).delete()
        for tid in tag_ids:
            db.session.add(NewsTagRelation(news_id=item_id, tag_id=tid))
        db.session.commit()

    return jsonify({'success': True, 'data': _news_detail(item_id), 'message': '更新成功'}), 200


@admin_bp.route('/news/<int:item_id>', methods=['DELETE'])
@jwt_required
def delete_news(item_id):
    item = News.query.get(item_id)
    if not item:
        raise NotFoundError('记录不存在')
    if g.current_user.role != 'admin' and item.status != 'draft':
        raise AppError('AUTH_ERROR', '仅可删除草稿', 403)
    admin_service.delete_item(News, item_id)
    return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200


@admin_bp.route('/news/<int:item_id>/approve', methods=['POST'])
@jwt_required(role='admin')
def approve_news(item_id):
    result = admin_service.approve_item(News, NewsDraft, item_id, 'news_id')
    return jsonify({'success': True, 'data': result, 'message': '审核通过'}), 200


@admin_bp.route('/news/<int:item_id>/suspend', methods=['POST'])
@jwt_required(role='admin')
def suspend_news(item_id):
    result = admin_service.suspend_item(News, NewsDraft, item_id, 'news_id')
    return jsonify({'success': True, 'data': result, 'message': '已挂起'}), 200


def _news_detail(item_id):
    text = NewsText.query.get(item_id)
    item = admin_service.get_item_with_draft(News, NewsDraft, item_id, 'news_id')
    item['item']['content'] = text.content if text else None
    return item


# ===================== Laws (dedicated, multipart + file + draft) =====================

@admin_bp.route('/laws', methods=['GET'])
@jwt_required
def list_laws():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    filters = {k: request.args.get(k) for k in [
        'country_id', 'scene_id', 'keyword',
    ] if request.args.get(k)}
    result = admin_service.list_items(Law, 'laws', page, per_page, status, filters)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/laws/<int:item_id>', methods=['GET'])
@jwt_required
def get_law(item_id):
    result = admin_service.get_item_with_draft(Law, LawDraft, item_id, 'law_id')
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/laws', methods=['POST'])
@jwt_required
def create_law():
    data = _parse_law_form()
    uploaded = request.files.get('file')
    if uploaded and uploaded.filename:
        data['secure_name'] = _save_uploaded_file(uploaded)
        data['filename'] = uploaded.filename

    result = admin_service.create_item(Law, data, g.current_user)
    return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201


@admin_bp.route('/laws/<int:item_id>', methods=['PUT'])
@jwt_required
def update_law(item_id):
    data = _parse_law_form()
    uploaded = request.files.get('file')

    if g.current_user.role == 'admin' and uploaded and uploaded.filename:
        old = Law.query.get(item_id)
        if old and old.secure_name:
            _remove_file(old.secure_name)
        data['secure_name'] = _save_uploaded_file(uploaded)
        data['filename'] = uploaded.filename

    result = admin_service.update_item_with_draft(Law, LawDraft, item_id, data, g.current_user, 'law_id')

    # editor file upload: save separately for draft/preview
    if g.current_user.role != 'admin' and uploaded and uploaded.filename:
        law = Law.query.get(item_id)
        draft = LawDraft.query.filter_by(law_id=item_id).first()
        if draft and law and law.status != 'draft':
            new_secure = _save_uploaded_file(uploaded)
            draft_data = dict(draft.data)
            draft_data['secure_name'] = new_secure
            draft_data['filename'] = uploaded.filename
            draft.data = draft_data
            db.session.commit()
            result['item']['secure_name'] = new_secure
            result['item']['filename'] = uploaded.filename
        elif law and law.status == 'draft':
            if law.secure_name:
                _remove_file(law.secure_name)
            law.secure_name = _save_uploaded_file(uploaded)
            law.filename = uploaded.filename
            db.session.commit()

    return jsonify({'success': True, 'data': result, 'message': '更新成功'}), 200


@admin_bp.route('/laws/<int:item_id>', methods=['DELETE'])
@jwt_required
def delete_law(item_id):
    law = Law.query.get(item_id)
    if not law:
        raise NotFoundError('记录不存在')
    if g.current_user.role != 'admin' and law.status != 'draft':
        raise AppError('AUTH_ERROR', '仅可删除草稿', 403)
    if law.secure_name:
        _remove_file(law.secure_name)
    admin_service.delete_item(Law, item_id)
    return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200


@admin_bp.route('/laws/<int:item_id>/approve', methods=['POST'])
@jwt_required(role='admin')
def approve_law(item_id):
    law = Law.query.get(item_id)
    old_secure = law.secure_name if law else None
    result = admin_service.approve_item(Law, LawDraft, item_id, 'law_id')
    new_secure = result['item'].get('secure_name')
    if old_secure and old_secure != new_secure:
        _remove_file(old_secure)
    return jsonify({'success': True, 'data': result, 'message': '审核通过'}), 200


@admin_bp.route('/laws/<int:item_id>/suspend', methods=['POST'])
@jwt_required(role='admin')
def suspend_law(item_id):
    result = admin_service.suspend_item(Law, LawDraft, item_id, 'law_id')
    return jsonify({'success': True, 'data': result, 'message': '已挂起'}), 200


def _parse_law_form():
    """Extract law text fields from request.form (multipart) or JSON."""
    if request.content_type and 'multipart' in request.content_type:
        form = request.form
    else:
        body = request.get_json(silent=True) or {}
        form = body

    fields = ['title_cn', 'title_en', 'law_number', 'country_id', 'scene_id',
              'effective_date', 'summary']
    return {k: form.get(k) for k in fields if form.get(k) is not None}


# ===================== Reference Tables (catch-all for admin CRUD) =====================

@admin_bp.route('/<string:resource>', methods=['GET'])
@jwt_required
def list_ref(resource):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    model = REF_MODELS[resource]
    result = admin_service.list_ref_items(model)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/<string:resource>/<string:item_id>', methods=['GET'])
@jwt_required
def get_ref(resource, item_id):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    model = REF_MODELS[resource]
    result = admin_service.get_ref_item(model, item_id)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/<string:resource>', methods=['POST'])
@jwt_required
def create_ref(resource):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    if resource in EDITOR_RESTRICTED and g.current_user.role != 'admin':
        raise AppError('AUTH_ERROR', '权限不足', 403)
    data = request.get_json(silent=True) or {}
    model = REF_MODELS[resource]
    result = admin_service.create_ref_item(model, data)
    return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201


@admin_bp.route('/<string:resource>/<string:item_id>', methods=['PUT'])
@jwt_required
def update_ref(resource, item_id):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    if resource in EDITOR_RESTRICTED and g.current_user.role != 'admin':
        raise AppError('AUTH_ERROR', '权限不足', 403)
    data = request.get_json(silent=True) or {}
    model = REF_MODELS[resource]
    result = admin_service.update_ref_item(model, item_id, data)
    return jsonify({'success': True, 'data': result, 'message': '更新成功'}), 200


@admin_bp.route('/<string:resource>/<string:item_id>', methods=['DELETE'])
@jwt_required(role='admin')
def delete_ref(resource, item_id):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    model = REF_MODELS[resource]
    admin_service.delete_ref_item(model, item_id)
    return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200


# ===================== User Management (admin only) =====================

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
