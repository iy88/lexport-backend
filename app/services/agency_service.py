from app.extensions import db
from app.models.agency import Agency, AgencyCategory, AgencyScene


def get_agencies(page=1, per_page=20, scene_id=None, category_id=None, keyword=None,
                 region=None):
    query = Agency.query.filter(Agency.status == 'published')

    if scene_id:
        query = query.filter(Agency.scene_id == scene_id)
    if category_id:
        scene_ids = [s.id for s in AgencyScene.query.filter_by(category_id=category_id).all()]
        query = query.filter(Agency.scene_id.in_(scene_ids))
    if region:
        query = query.filter(Agency.region.contains(region))
    if keyword:
        query = query.filter(
            db.or_(Agency.name.contains(keyword), Agency.region.contains(keyword))
        )

    total = query.count()

    agencies = (
        query
        .order_by(Agency.sort_order)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    categories = AgencyCategory.query.order_by(AgencyCategory.sort_order).all()
    scenes = AgencyScene.query.order_by(AgencyScene.sort_order).all()

    return {
        'agencies': [_to_dict(a) for a in agencies],
        'meta': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'categories': [
                {
                    'id': c.id,
                    'label_zh': c.label_zh,
                    'icon_name': c.icon_name,
                    'scenes': [
                        {'id': s.id, 'label_zh': s.label_zh}
                        for s in scenes if s.category_id == c.id
                    ],
                }
                for c in categories
            ],
        },
    }


def _to_dict(a):
    return {
        'id': a.id,
        'name': a.name,
        'scene_id': a.scene_id,
        'region': a.region,
        'phone': a.phone,
        'email': a.email,
        'business': a.business,
        'advantage': a.advantage,
        'highlight': a.highlight,
        'sort_order': a.sort_order,
    }
