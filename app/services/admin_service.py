from app.extensions import db
from app.models.agency import AgencyCategory, AgencyScene
from app.models.country import Country
from app.models.draft import LawDraft, NewsDraft, AgencyDraft
from app.models.law import ComplianceScene
from app.models.news import NewsTag
from app.utils.errors import NotFoundError


# -- Reference data helpers --

def _ref_data(resource):
    if resource in ('laws', 'admin/laws'):
        return {
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in Country.query.order_by(Country.sort_order).all()],
            'scenes': [{'id': s.id, 'label_zh': s.label_zh} for s in
                       ComplianceScene.query.order_by(ComplianceScene.sort_order).all()],
        }
    if resource in ('news', 'admin/news'):
        return {
            'types': [
                {'value': 'cooperation', 'label_zh': '中非合作'},
                {'value': 'hotspot', 'label_zh': '合规热点'},
                {'value': 'update', 'label_zh': '法规更新'},
            ],
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in Country.query.order_by(Country.sort_order).all()],
            'tags': [{'id': t.id, 'name_zh': t.name_zh} for t in NewsTag.query.order_by(NewsTag.id).all()],
        }
    if resource in ('agencies', 'admin/agencies'):
        categories = AgencyCategory.query.order_by(AgencyCategory.sort_order).all()
        scenes = AgencyScene.query.order_by(AgencyScene.sort_order).all()
        return {
            'categories': [
                {
                    'id': c.id, 'label_zh': c.label_zh, 'icon_name': c.icon_name,
                    'scenes': [{'id': s.id, 'label_zh': s.label_zh} for s in scenes if s.category_id == c.id],
                }
                for c in categories
            ],
        }
    return {}


# -- Generic content table CRUD (with draft support) --

def list_items(model, resource, page=1, per_page=20, status=None, filters=None):
    query = model.query
    if status:
        query = query.filter(model.status == status)
    if filters:
        for field, value in filters.items():
            if hasattr(model, field) and value is not None:
                attr = getattr(model, field)
                # date range fields: field_from / field_to
                if field.endswith('_from') and hasattr(model, field.replace('_from', '')):
                    real_attr = getattr(model, field.replace('_from', ''))
                    query = query.filter(real_attr >= value)
                elif field.endswith('_to') and hasattr(model, field.replace('_to', '')):
                    real_attr = getattr(model, field.replace('_to', ''))
                    query = query.filter(real_attr <= value)
                elif isinstance(attr.property.columns[0].type, db.String):
                    query = query.filter(attr.contains(value))
                else:
                    query = query.filter(attr == value)
    query = query.order_by(model.id.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        'items': [_admin_to_dict(item) for item in items],
        'meta': {
            'page': page, 'per_page': per_page, 'total': total,
            **_ref_data(resource),
        },
    }


def get_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    return {'item': _admin_to_dict(item)}


def get_item_with_draft(model, DraftModel, item_id, fk_field):
    """Get item with draft preview merged in."""
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')

    result = _admin_to_dict(item)

    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
    if draft and draft.data:
        # overlay draft data on top of real column values
        preview = dict(result)
        preview.update(draft.data)
        result = preview

    return {'item': result}


def create_item(model, data, user):
    item = model(**data)
    if user.role != 'admin':
        item.status = 'draft'
    db.session.add(item)
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def suspend_item(model, DraftModel, item_id, fk_field):
    """Set published item back to draft (admin only)."""
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
    if draft:
        db.session.delete(draft)
    item.status = 'draft'
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def update_item_with_draft(model, DraftModel, item_id, data, user, fk_field):
    """Update with draft support:
    - admin: direct update
    - editor on published: save to draft table
    - editor on own draft: direct update
    """
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')

    if user.role == 'admin':
        # admin: direct update
        for key, value in data.items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.status = data.get('status', item.status)
        db.session.commit()
    else:
        # editor logic
        if item.status == 'draft':
            # own draft: direct update
            for key, value in data.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            item.status = 'draft'
            db.session.commit()
        else:
            # published record: save to draft table
            full_data = _admin_to_dict(item)
            full_data.pop('created_at', None)
            full_data.pop('updated_at', None)
            full_data.pop('id', None)
            full_data.update(data)

            draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
            if draft:
                draft.data = full_data
                draft.editor_id = user.id
            else:
                draft = DraftModel(**{fk_field: item_id, 'data': full_data, 'editor_id': user.id})
                db.session.add(draft)
            item.status = 'draft'
            db.session.commit()

    return {'item': _admin_to_dict(item)}


def delete_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    db.session.delete(item)
    db.session.commit()


def approve_item(model, DraftModel, item_id, fk_field):
    """Approve draft: merge draft data into main row, delete draft."""
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')

    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
    if draft and draft.data:
        for key, value in draft.data.items():
            if hasattr(item, key):
                setattr(item, key, value)
        db.session.delete(draft)

    item.status = 'published'
    db.session.commit()
    return {'item': _admin_to_dict(item)}


# -- Reference table CRUD (no status, no draft) --

def list_ref_items(model):
    items = model.query.order_by(model.id).all()
    return {
        'items': [_admin_to_dict(item) for item in items],
    }


def get_ref_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    return {'item': _admin_to_dict(item)}


def create_ref_item(model, data):
    item = model(**data)
    db.session.add(item)
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def update_ref_item(model, item_id, data):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def delete_ref_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    db.session.delete(item)
    db.session.commit()


# -- Serializer --

def _admin_to_dict(item):
    d = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        d[col.name] = val
    return d
