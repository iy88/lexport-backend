from app.extensions import db
from app.models.content import NewsText
from app.models.country import Country
from app.models.news import News, NewsTag, NewsTagRelation
from app.services.admin_service import _parse_date
from app.utils.errors import NotFoundError, ValidationError


def get_news(page=1, per_page=20, type=None, country_id=None, keyword=None,
             date_from=None, date_to=None, tag_id=None):
    query = News.query.filter(News.status == 'published')

    parsed_from = _parse_date(date_from, 'date_from') if date_from else None
    parsed_to = _parse_date(date_to, 'date_to') if date_to else None
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise ValidationError('date_from 不能晚于 date_to')

    if type:
        if type not in ('cooperation', 'hotspot', 'update'):
            raise ValidationError('无效的资讯类型')
        query = query.filter(News.type == type)
    if country_id:
        query = query.filter(News.country_id == country_id)
    if parsed_from:
        query = query.filter(News.date >= parsed_from)
    if parsed_to:
        query = query.filter(News.date <= parsed_to)
    if keyword:
        query = query.filter(News.title.contains(keyword))
    if tag_id:
        query = query.filter(NewsTagRelation.query.filter(
            NewsTagRelation.news_id == News.id,
            NewsTagRelation.tag_id == tag_id,
        ).exists())

    # Tags are a small reference table; do not enumerate every matching News ID.
    meta_tags = [{'id': t.id, 'name_zh': t.name_zh}
                 for t in NewsTag.query.order_by(NewsTag.id).all()]

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
            tag = tags.get(r.tag_id)
            if tag:
                tag_map.setdefault(r.news_id, []).append({'id': r.tag_id, 'name_zh': tag.name_zh})

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
    item = News.query.filter_by(id=news_id, status='published').first()
    if not item:
        raise NotFoundError('资讯不存在')

    # get tags
    relations = NewsTagRelation.query.filter_by(news_id=news_id).all()
    tag_ids = [r.tag_id for r in relations]
    tags = NewsTag.query.filter(NewsTag.id.in_(tag_ids)).all() if tag_ids else []
    tag_list = [{'id': t.id, 'name_zh': t.name_zh} for t in tags]

    # get content
    text = db.session.get(NewsText, news_id)
    content = text.content if text else None

    return {
        **_to_dict(item, tag_list),
        'content': content,
    }
