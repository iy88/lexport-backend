from sqlalchemy import or_

from app.models.country import Country
from app.models.law import Law, ComplianceScene


def get_laws(page=1, per_page=20, country_id=None, scene_id=None, keyword=None):
    query = Law.query.filter(Law.status == 'published')

    if country_id:
        query = query.filter(Law.country_id == country_id)
    if scene_id:
        query = query.filter(Law.scene_id == scene_id)
    if keyword:
        query = query.filter(or_(
            Law.title_cn.contains(keyword),
            Law.title_en.contains(keyword),
        ))

    total = query.count()

    laws = (
        query
        .order_by(Law.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    countries = Country.query.order_by(Country.sort_order).all()
    scenes = ComplianceScene.query.order_by(ComplianceScene.sort_order).all()

    return {
        'laws': [_law_to_dict(l) for l in laws],
        'meta': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in countries],
            'scenes': [{'id': s.id, 'label_zh': s.label_zh} for s in scenes],
        },
    }


def _law_to_dict(law):
    return {
        'id': law.id,
        'title_cn': law.title_cn,
        'title_en': law.title_en,
        'law_number': law.law_number,
        'country_id': law.country_id,
        'scene_id': law.scene_id,
        'effective_date': law.effective_date.isoformat() if law.effective_date else None,
        'summary': law.summary,
        'filename': law.filename,
        'secure_name': law.secure_name,
        'created_at': law.created_at.isoformat() if law.created_at else None,
    }
