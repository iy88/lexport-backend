from flask import Blueprint, request, jsonify, g

from app.extensions import db
from app.models.agency import Agency, AgencyCategory, AgencyScene
from app.models.content import NewsText
from app.models.country import Country
from app.models.draft import NewsDraft, AgencyDraft
from app.models.law import ComplianceScene, Law
from app.models.news import News, NewsTag, NewsTagRelation
from app.models.user import User
from app.services import admin_service, law_service
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
    'news-tags': NewsTag,
}

EDITOR_RESTRICTED = set()


# ===================== Agencies (content, generic) =====================

@admin_bp.route('/agencies', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def list_agencies():
    page, per_page = _pagination()
    status = request.args.get('status')
    review_status = request.args.get('review_status')
    filters = {k: request.args.get(k) for k in [
        'scene_id', 'category_id', 'region', 'keyword',
    ] if request.args.get(k)}
    model, _, _ = CONTENT_MODELS['agencies']
    result = admin_service.list_items(model, 'agencies', page, per_page, status,
                                      review_status=review_status, filters=filters)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/agencies/<int:item_id>', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def get_agency(item_id):
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.get_item_with_draft(model, draft_model, item_id, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/agencies', methods=['POST'])
@jwt_required(roles=('admin', 'editor'))
def create_agency():
    data = _json_body()
    model, _, _ = CONTENT_MODELS['agencies']
    result = admin_service.create_item(model, data, g.current_user)
    return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201


@admin_bp.route('/agencies/<int:item_id>', methods=['PUT'])
@jwt_required(roles=('admin', 'editor'))
def update_agency(item_id):
    data = _json_body()
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.update_item_with_draft(model, draft_model, item_id, data, g.current_user, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '更新成功'}), 200


@admin_bp.route('/agencies/<int:item_id>', methods=['DELETE'])
@jwt_required(roles=('admin', 'editor'))
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


@admin_bp.route('/agencies/approve-batch', methods=['POST'])
@jwt_required(role='admin')
def batch_approve_agency():
    data = _json_body()
    ids = data.get('ids', [])
    if not ids:
        raise AppError('VALIDATION_ERROR', 'ids 不能为空', 400)
    if not isinstance(ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in ids):
        raise AppError('VALIDATION_ERROR', 'ids 必须为整数数组', 400)
    ids = list(dict.fromkeys(ids))
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.batch_approve_items(model, draft_model, ids, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '批量审核完成'}), 200


@admin_bp.route('/agencies/<int:item_id>/suspend', methods=['POST'])
@jwt_required(role='admin')
def suspend_agency(item_id):
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    result = admin_service.suspend_item(model, draft_model, item_id, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '已挂起'}), 200


@admin_bp.route('/agencies/<int:item_id>/draft', methods=['DELETE'])
@jwt_required(role='admin')
def discard_agency_draft(item_id):
    """Discard a pending AgencyDraft, keeping the published main version."""
    model, draft_model, fk_field = CONTENT_MODELS['agencies']
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = draft_model.query.filter_by(**{fk_field: item_id}).first()
    if not draft:
        raise AppError('VALIDATION_ERROR', '该机构没有待审核修改', 400)
    db.session.delete(draft)
    db.session.commit()
    result = admin_service.get_item_with_draft(model, draft_model, item_id, fk_field)
    return jsonify({'success': True, 'data': result, 'message': '草稿已丢弃'}), 200


# ===================== News (dedicated, content + draft) =====================

@admin_bp.route('/news', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def list_news():
    page, per_page = _pagination()
    status = request.args.get('status')
    review_status = request.args.get('review_status')
    tag_id = _optional_int_arg('tag_id')
    filters = {k: request.args.get(k) for k in [
        'type', 'country_id', 'date_from', 'date_to', 'keyword',
    ] if request.args.get(k)}
    result = admin_service.list_items(News, 'news', page, per_page, status,
                                      review_status=review_status, filters=filters,
                                      tag_id=tag_id)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/news/<int:item_id>', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def get_news(item_id):
    result = _news_detail(item_id)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/news', methods=['POST'])
@jwt_required(roles=('admin', 'editor'))
def create_news():
    data = _json_body()
    item_id = admin_service.create_news(data, g.current_user)
    return jsonify({'success': True, 'data': _news_detail(item_id), 'message': '创建成功'}), 201


@admin_bp.route('/news/<int:item_id>', methods=['PUT'])
@jwt_required(roles=('admin', 'editor'))
def update_news(item_id):
    data = _json_body()
    admin_service.update_news(item_id, data, g.current_user)
    return jsonify({'success': True, 'data': _news_detail(item_id), 'message': '更新成功'}), 200


@admin_bp.route('/news/<int:item_id>', methods=['DELETE'])
@jwt_required(roles=('admin', 'editor'))
def delete_news(item_id):
    item = db.session.get(News, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    if g.current_user.role != 'admin' and item.status != 'draft':
        raise AppError('AUTH_ERROR', '仅可删除草稿', 403)
    admin_service.delete_item(News, item_id)
    return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200


@admin_bp.route('/news/<int:item_id>/approve', methods=['POST'])
@jwt_required(role='admin')
def approve_news(item_id):
    admin_service.approve_news(item_id)
    return jsonify({'success': True, 'data': _news_detail(item_id), 'message': '审核通过'}), 200


@admin_bp.route('/news/<int:item_id>/draft', methods=['DELETE'])
@jwt_required(role='admin')
def discard_news_draft(item_id):
    """Discard a pending NewsDraft, keeping the published main version."""
    item = db.session.get(News, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = NewsDraft.query.filter_by(news_id=item_id).first()
    if not draft:
        raise AppError('VALIDATION_ERROR', '该资讯没有待审核修改', 400)
    db.session.delete(draft)
    db.session.commit()
    return jsonify({'success': True, 'data': _news_detail(item_id), 'message': '草稿已丢弃'}), 200


@admin_bp.route('/news/approve-batch', methods=['POST'])
@jwt_required(role='admin')
def batch_approve_news():
    data = _json_body()
    ids = data.get('ids', [])
    if not ids:
        raise AppError('VALIDATION_ERROR', 'ids 不能为空', 400)
    if not isinstance(ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in ids):
        raise AppError('VALIDATION_ERROR', 'ids 必须为整数数组', 400)
    result = admin_service.batch_approve_news(list(dict.fromkeys(ids)))
    return jsonify({'success': True, 'data': result, 'message': '批量审核完成'}), 200


@admin_bp.route('/news/<int:item_id>/suspend', methods=['POST'])
@jwt_required(role='admin')
def suspend_news(item_id):
    result = admin_service.suspend_item(News, NewsDraft, item_id, 'news_id')
    return jsonify({'success': True, 'data': result, 'message': '已挂起'}), 200


def _news_detail(item_id):
    text = db.session.get(NewsText, item_id)
    item = admin_service.get_item_with_draft(News, NewsDraft, item_id, 'news_id')

    # Merge live content only if the draft preview did not supply it.
    if 'content' not in item['item']:
        item['item']['content'] = text.content if text else None

    # Resolve tags from DB for current state, or from draft tag_ids for preview
    draft = NewsDraft.query.filter_by(news_id=item_id).first()
    if (draft and isinstance(draft.data, dict) and
            draft.data.get('tag_ids') is not None):
        draft_tag_ids = admin_service.validate_tag_ids(draft.data['tag_ids'])
        if draft_tag_ids:
            tags = NewsTag.query.filter(NewsTag.id.in_(draft_tag_ids)).all()
            item['item']['tags'] = [{'id': t.id, 'name_zh': t.name_zh} for t in tags]
        else:
            item['item']['tags'] = []
    else:
        relations = NewsTagRelation.query.filter_by(news_id=item_id).all()
        tag_ids = [r.tag_id for r in relations]
        if tag_ids:
            tags = NewsTag.query.filter(NewsTag.id.in_(tag_ids)).all()
            item['item']['tags'] = [{'id': t.id, 'name_zh': t.name_zh} for t in tags]
        else:
            item['item']['tags'] = []

    return item


def _pagination():
    page = request.args.get('page', 1, type=int) or 1
    per_page = request.args.get('per_page', 20, type=int) or 20
    return max(1, page), min(100, max(1, per_page))


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError('VALIDATION_ERROR', '请求体必须为 JSON 对象', 400)
    return data


def _optional_int_arg(name):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AppError('VALIDATION_ERROR', f'{name} 必须为整数', 400) from exc
    if value <= 0:
        raise AppError('VALIDATION_ERROR', f'{name} 必须为正整数', 400)
    return value


# ===================== Laws (dedicated, multipart + file + draft + OSS) =====================


@admin_bp.route('/laws', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def list_laws():
    page, per_page = _pagination()
    status = request.args.get('status')
    review_status = request.args.get('review_status')
    filters = {k: request.args.get(k) for k in [
        'country_id', 'scene_id', 'keyword',
    ] if request.args.get(k)}
    result = law_service.list_laws(
        page=page, per_page=per_page, status=status,
        review_status=review_status, filters=filters,
    )
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/laws/<int:item_id>', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def get_law(item_id):
    result = law_service.get_law_with_draft(item_id)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/laws', methods=['POST'])
@jwt_required(roles=('admin', 'editor'))
def create_law():
    data = _parse_law_form()
    uploaded = request.files.get('file')
    result = law_service.create_law(data, uploaded, g.current_user)
    return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201


@admin_bp.route('/laws/<int:item_id>', methods=['PUT'])
@jwt_required(roles=('admin', 'editor'))
def update_law(item_id):
    data = _parse_law_form()
    uploaded = request.files.get('file')
    try:
        result = law_service.update_law(item_id, data, uploaded, g.current_user)
        return jsonify({'success': True, 'data': result, 'message': '更新成功'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/laws/<int:item_id>', methods=['DELETE'])
@jwt_required(roles=('admin', 'editor'))
def delete_law(item_id):
    law = db.session.get(Law, item_id)
    if not law:
        raise NotFoundError('记录不存在')
    if g.current_user.role != 'admin' and law.status != 'draft':
        raise AppError('AUTH_ERROR', '仅可删除草稿', 403)
    try:
        law_service.delete_law(item_id, g.current_user)
    except AppError as e:
        return e.to_response()
    return jsonify({'success': True, 'data': None, 'message': '删除成功'}), 200


@admin_bp.route('/laws/<int:item_id>/approve', methods=['POST'])
@jwt_required(role='admin')
def approve_law(item_id):
    try:
        result = law_service.approve_law(item_id)
        return jsonify({'success': True, 'data': result, 'message': '审核通过'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/laws/approve-batch', methods=['POST'])
@jwt_required(role='admin')
def batch_approve_law():
    data = _json_body()
    ids = data.get('ids', [])
    if (not isinstance(ids, list) or not ids or
            any(isinstance(item_id, bool) or not isinstance(item_id, int)
                for item_id in ids)):
        raise AppError('VALIDATION_ERROR', 'ids 必须为非空整数数组', 400)
    result = law_service.batch_approve_laws(list(dict.fromkeys(ids)))
    return jsonify({'success': True, 'data': result, 'message': '批量审核完成'}), 200


@admin_bp.route('/laws/<int:item_id>/suspend', methods=['POST'])
@jwt_required(role='admin')
def suspend_law(item_id):
    try:
        result = law_service.suspend_law(item_id)
        return jsonify({'success': True, 'data': result, 'message': '已挂起'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/laws/<int:item_id>/draft', methods=['DELETE'])
@jwt_required(role='admin')
def discard_law_draft(item_id):
    """Discard a pending LawDraft, keeping the published main version."""
    try:
        result = law_service.discard_law_draft(item_id)
        return jsonify({'success': True, 'data': result, 'message': '草稿已丢弃'}), 200
    except AppError as e:
        return e.to_response()


def _parse_law_form():
    """Extract law text fields from request.form (multipart) or JSON."""
    if request.content_type and 'multipart' in request.content_type:
        form = request.form
    else:
        form = _json_body()

    fields = ['title_cn', 'title_en', 'law_number', 'country_id', 'scene_id',
              'effective_date', 'summary']
    return {k: form.get(k) for k in fields if form.get(k) is not None}


# ===================== Compliance Reports (admin, dedicated) =====================


@admin_bp.route('/compliance-reports', methods=['GET'])
@jwt_required(role='admin')
def list_compliance_reports():
    """List all compliance reports including soft-deleted."""
    from app.services import compliance_service
    page = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int) or 20))
    result = compliance_service.list_all_reports(page=page, per_page=per_page)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/compliance-reports/<int:report_id>', methods=['GET'])
@jwt_required(role='admin')
def get_compliance_report(report_id):
    """Get any compliance report detail including soft-deleted."""
    from app.services import compliance_service
    try:
        result = compliance_service.get_any_report(report_id)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@admin_bp.route('/compliance-reports/<int:report_id>', methods=['DELETE'])
@jwt_required(role='admin')
def delete_compliance_report(report_id):
    """Soft-delete any compliance report."""
    from app.services import compliance_service
    try:
        result = compliance_service.admin_delete_report(report_id)
        return jsonify({'success': True, 'data': result, 'message': '报告已删除'}), 200
    except AppError as e:
        return e.to_response()


# ===================== Reference Tables (catch-all for admin CRUD) =====================

@admin_bp.route('/<string:resource>', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def list_ref(resource):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    model = REF_MODELS[resource]
    result = admin_service.list_ref_items(model)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/<string:resource>/<string:item_id>', methods=['GET'])
@jwt_required(roles=('admin', 'editor'))
def get_ref(resource, item_id):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    model = REF_MODELS[resource]
    result = admin_service.get_ref_item(model, item_id)
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@admin_bp.route('/<string:resource>', methods=['POST'])
@jwt_required(roles=('admin', 'editor'))
def create_ref(resource):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    if resource in EDITOR_RESTRICTED and g.current_user.role != 'admin':
        raise AppError('AUTH_ERROR', '权限不足', 403)
    data = _json_body()
    model = REF_MODELS[resource]
    result = admin_service.create_ref_item(model, data)
    return jsonify({'success': True, 'data': result, 'message': '创建成功'}), 201


@admin_bp.route('/<string:resource>/<string:item_id>', methods=['PUT'])
@jwt_required(roles=('admin', 'editor'))
def update_ref(resource, item_id):
    if resource not in REF_MODELS:
        raise NotFoundError('资源不存在')
    if resource in EDITOR_RESTRICTED and g.current_user.role != 'admin':
        raise AppError('AUTH_ERROR', '权限不足', 403)
    data = _json_body()
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
    page, per_page = _pagination()
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
    data = _json_body()
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
