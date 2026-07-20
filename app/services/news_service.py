from app.models.content import NewsText
from app.models.country import Country
from app.models.news import News, NewsTag, NewsTagRelation
from app.utils.errors import NotFoundError


def get_news(page=1, per_page=20, type=None, country_id=None, keyword=None,
             date_from=None, date_to=None, tag_id=None):
    query = News.query.filter(News.status == 'published')

    if type:
        query = query.filter(News.type == type)
    if country_id:
        query = query.filter(News.country_id == country_id)
    if date_from:
        query = query.filter(News.date >= date_from)
    if date_to:
        query = query.filter(News.date <= date_to)
    if keyword:
        query = query.filter(News.title.contains(keyword))
    if tag_id:
        tagged_ids = [r.news_id for r in NewsTagRelation.query.filter_by(tag_id=tag_id).all()]
        query = query.filter(News.id.in_(tagged_ids))

    # collect tags from all matching results (before pagination)
    all_matching_ids = [n[0] for n in query.with_entities(News.id).all()]
    all_tag_ids = set()
    if all_matching_ids:
        for r in NewsTagRelation.query.filter(NewsTagRelation.news_id.in_(all_matching_ids)).all():
            all_tag_ids.add(r.tag_id)
    meta_tags = [{'id': t.id, 'name_zh': t.name_zh}
                 for t in NewsTag.query.filter(NewsTag.id.in_(all_tag_ids)).order_by(NewsTag.id).all()] if all_tag_ids else []

    total = query.count()

    news_list = (
        query
        .order_by(News.date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # collect tags for current page news
    news_ids = [n.id for n in news_list]
    tag_map = {}
    if news_ids:
        relations = NewsTagRelation.query.filter(NewsTagRelation.news_id.in_(news_ids)).all()
        page_tag_ids = {r.tag_id for r in relations}
        tags = {t.id: t for t in NewsTag.query.filter(NewsTag.id.in_(page_tag_ids)).all()}
        for r in relations:
            tag_map.setdefault(r.news_id, []).append({'id': r.tag_id, 'name_zh': tags[r.tag_id].name_zh})

    countries = Country.query.order_by(Country.sort_order).all()

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
            'tags': meta_tags,
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


def get_news_detail(news_id):
    item = News.query.get(news_id)
    if not item:
        raise NotFoundError('资讯不存在')

    # get tags
    relations = NewsTagRelation.query.filter_by(news_id=news_id).all()
    tag_ids = [r.tag_id for r in relations]
    tags = NewsTag.query.filter(NewsTag.id.in_(tag_ids)).all() if tag_ids else []
    tag_list = [{'id': t.id, 'name_zh': t.name_zh} for t in tags]

    # get content
    text = NewsText.query.get(news_id)
    content = text.content if text else None

    return {
        **_to_dict(item, tag_list),
        'content': content,
    }
