from app.models.country import Country
from app.models.news import News, NewsTag, NewsTagRelation


def get_news(page=1, per_page=20, type=None, country_id=None, keyword=None):
    query = News.query.filter(News.status == 'published')

    if type:
        query = query.filter(News.type == type)
    if country_id:
        query = query.filter(News.country_id == country_id)
    if keyword:
        query = query.filter(News.title.contains(keyword))

    total = query.count()

    news_list = (
        query
        .order_by(News.date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # collect tags for returned news
    news_ids = [n.id for n in news_list]
    tag_map = {}
    if news_ids:
        relations = NewsTagRelation.query.filter(NewsTagRelation.news_id.in_(news_ids)).all()
        tag_ids = {r.tag_id for r in relations}
        tags = {t.id: t for t in NewsTag.query.filter(NewsTag.id.in_(tag_ids)).all()}
        for r in relations:
            tag_map.setdefault(r.news_id, []).append({'id': r.tag_id, 'name_zh': tags[r.tag_id].name_zh})

    countries = Country.query.order_by(Country.sort_order).all()
    all_tags = NewsTag.query.order_by(NewsTag.id).all()

    return {
        'news': [_to_dict(n, tag_map.get(n.id, [])) for n in news_list],
        'meta': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'types': [
                {'value': 'cooperation', 'label_zh': '中非合作'},
                {'value': 'hotspot', 'label_zh': '合规热点'},
                {'value': 'update', 'label_zh': '法规更新'},
            ],
            'countries': [{'id': c.id, 'name_zh': c.name_zh} for c in countries],
            'tags': [{'id': t.id, 'name_zh': t.name_zh} for t in all_tags],
        },
    }


def _to_dict(n, tags):
    return {
        'id': n.id,
        'type': n.type,
        'title': n.title,
        'source': n.source,
        'country_id': n.country_id,
        'date': n.date.isoformat() if n.date else None,
        'summary': n.summary,
        'risk_level': n.risk_level,
        'involved_laws': n.involved_laws,
        'response': n.response,
        'update_type': n.update_type,
        'change_desc': n.change_desc,
        'impact': n.impact,
        'advice': n.advice,
        'tags': tags,
        'created_at': n.created_at.isoformat() if n.created_at else None,
    }
