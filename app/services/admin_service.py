from app.extensions import db
from app.utils.errors import NotFoundError
from app.models.law import ComplianceScene
from app.models.country import Country
from app.models.news import NewsTag
from app.models.agency import AgencyCategory, AgencyScene


def list_items(model, resource, page=1, per_page=20, status=None):
    query = model.query
    if status:
        query = query.filter(model.status == status)
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


def _ref_data(resource):
    if resource == 'laws':
        return {
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in Country.query.order_by(Country.sort_order).all()],
            'scenes': [{'id': s.id, 'label_zh': s.label_zh} for s in ComplianceScene.query.order_by(ComplianceScene.sort_order).all()],
        }
    if resource == 'news':
        return {
            'types': [
                {'value': 'cooperation', 'label_zh': '中非合作'},
                {'value': 'hotspot', 'label_zh': '合规热点'},
                {'value': 'update', 'label_zh': '法规更新'},
            ],
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in Country.query.order_by(Country.sort_order).all()],
            'tags': [{'id': t.id, 'name_zh': t.name_zh} for t in NewsTag.query.order_by(NewsTag.id).all()],
        }
    if resource == 'agencies':
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


def get_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    return {'item': _admin_to_dict(item)}


def create_item(model, data, user):
    item = model(**data)
    if user.role != 'admin':
        item.status = 'draft'
    db.session.add(item)
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def update_item(model, item_id, data, user):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    if user.role != 'admin':
        item.status = 'draft'
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def delete_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    db.session.delete(item)
    db.session.commit()


def approve_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    item.status = 'published'
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def _admin_to_dict(item):
    d = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        d[col.name] = val
    return d
