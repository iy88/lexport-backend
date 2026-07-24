from datetime import date

from sqlalchemy.exc import DataError, IntegrityError, StatementError

from app.extensions import db
from app.models.agency import Agency, AgencyCategory, AgencyScene
from app.models.content import NewsText
from app.models.country import Country
from app.models.draft import LawDraft, NewsDraft, AgencyDraft
from app.models.law import ComplianceScene
from app.models.news import News, NewsTag, NewsTagRelation
from app.utils.errors import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.utils.validators import normalize_model_strings


EDITABLE_FIELDS = {
    'agencies': {'name', 'scene_id', 'region', 'phone', 'email', 'business',
                 'advantage', 'highlight', 'sort_order'},
    'news': {'type', 'title', 'source', 'country_id', 'date', 'summary',
             'risk_level', 'involved_laws', 'response', 'update_type',
             'change_desc', 'impact', 'advice'},
}

REF_CREATE_FIELDS = {
    'countries': {'id', 'name_zh', 'name_en', 'sort_order'},
    'compliance_scenes': {'id', 'label_zh', 'sort_order'},
    'agency_categories': {'id', 'label_zh', 'icon_name', 'sort_order'},
    'agency_scenes': {'id', 'category_id', 'label_zh', 'sort_order'},
    'news_tags': {'name_zh'},
}


def _ref_data(resource):
    if resource in ('laws', 'admin/laws'):
        return {
            'countries': [
                {'id': c.id, 'name_zh': c.name_zh}
                for c in Country.query.order_by(Country.sort_order).all()
            ],
            'scenes': [
                {'id': s.id, 'label_zh': s.label_zh}
                for s in ComplianceScene.query.order_by(
                    ComplianceScene.sort_order,
                ).all()
            ],
        }
    if resource in ('news', 'admin/news'):
        return {
            'types': [
                {'value': 'cooperation', 'label_zh': '中非合作'},
                {'value': 'hotspot', 'label_zh': '合规热点'},
                {'value': 'update', 'label_zh': '法规更新'},
            ],
            'countries': [
                {'id': c.id, 'name_zh': c.name_zh}
                for c in Country.query.order_by(Country.sort_order).all()
            ],
            'tags': [{'id': t.id, 'name_zh': t.name_zh} for t in NewsTag.query.order_by(NewsTag.id).all()],
        }
    if resource in ('agencies', 'admin/agencies'):
        categories = AgencyCategory.query.order_by(AgencyCategory.sort_order).all()
        scenes = AgencyScene.query.order_by(AgencyScene.sort_order).all()
        return {'categories': [{
            'id': c.id, 'label_zh': c.label_zh, 'icon_name': c.icon_name,
            'scenes': [{'id': s.id, 'label_zh': s.label_zh} for s in scenes if s.category_id == c.id],
        } for c in categories]}
    return {}


def _draft_spec(resource):
    return {
        'laws': (LawDraft, LawDraft.law_id),
        'admin/laws': (LawDraft, LawDraft.law_id),
        'news': (NewsDraft, NewsDraft.news_id),
        'admin/news': (NewsDraft, NewsDraft.news_id),
        'agencies': (AgencyDraft, AgencyDraft.agency_id),
        'admin/agencies': (AgencyDraft, AgencyDraft.agency_id),
    }.get(resource)


def list_items(model, resource, page=1, per_page=20, status=None, review_status=None,
               filters=None, tag_id=None):
    if status not in (None, 'draft', 'published'):
        raise ValidationError('status 必须为 draft 或 published')
    if review_status not in (None, 'pending', 'none'):
        raise ValidationError('review_status 必须为 pending 或 none')

    query = model.query
    if status:
        query = query.filter(model.status == status)

    draft_spec = _draft_spec(resource)
    if review_status and draft_spec:
        draft_model, fk_col = draft_spec
        has_draft = db.session.query(draft_model.id).filter(fk_col == model.id).exists()
        pending = db.or_(model.status == 'draft', has_draft)
        query = query.filter(pending if review_status == 'pending' else db.not_(pending))

    if tag_id is not None:
        query = query.filter(NewsTagRelation.query.filter(
            NewsTagRelation.news_id == model.id,
            NewsTagRelation.tag_id == tag_id,
        ).exists())

    filters = filters or {}
    if resource in ('news', 'admin/news'):
        parsed_from = _parse_date(filters['date_from'], 'date_from') if filters.get('date_from') else None
        parsed_to = _parse_date(filters['date_to'], 'date_to') if filters.get('date_to') else None
        if parsed_from and parsed_to and parsed_from > parsed_to:
            raise ValidationError('date_from 不能晚于 date_to')
        if filters.get('type'):
            if filters['type'] not in ('cooperation', 'hotspot', 'update'):
                raise ValidationError('无效的资讯类型')
            query = query.filter(News.type == filters['type'])
        if filters.get('country_id'):
            query = query.filter(News.country_id == filters['country_id'])
        if parsed_from:
            query = query.filter(News.date >= parsed_from)
        if parsed_to:
            query = query.filter(News.date <= parsed_to)
        if filters.get('keyword'):
            keyword = filters['keyword']
            query = query.filter(db.or_(News.title.contains(keyword), News.summary.contains(keyword)))
    elif resource in ('agencies', 'admin/agencies'):
        if filters.get('scene_id'):
            query = query.filter(Agency.scene_id == filters['scene_id'])
        if filters.get('category_id'):
            query = query.filter(AgencyScene.query.filter(
                AgencyScene.id == Agency.scene_id,
                AgencyScene.category_id == filters['category_id'],
            ).exists())
        if filters.get('region'):
            query = query.filter(Agency.region.contains(filters['region']))
        if filters.get('keyword'):
            keyword = filters['keyword']
            query = query.filter(db.or_(Agency.name.contains(keyword), Agency.region.contains(keyword)))

    query = query.order_by(model.id.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    draft_map = {}
    if items and draft_spec:
        draft_model, fk_col = draft_spec
        drafts = draft_model.query.filter(fk_col.in_([item.id for item in items])).all()
        draft_map = {getattr(draft, fk_col.key): draft for draft in drafts}

    return {
        'items': [_admin_to_dict(item, draft_map.get(item.id)) for item in items],
        'meta': {'page': page, 'per_page': per_page, 'total': total, **_ref_data(resource)},
    }


def get_item_with_draft(model, DraftModel, item_id, fk_field):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
    result = _admin_to_dict(item, draft)
    live_status = result.get('status')
    if draft and draft.data:
        resource = 'news' if model is News else 'agencies'
        result.update(_draft_payload(resource, draft.data))
        result['status'] = live_status
        result['has_draft'] = True
        result['review_status'] = 'pending'
    return {'item': result}


def create_item(model, data, user):
    if model is not Agency:
        raise ValidationError('不支持的资源')
    if user.role not in ('admin', 'editor'):
        raise AuthenticationError('权限不足', http_status=403)
    values = validate_agency_data(data, partial=False)
    item = Agency(**values, status='draft' if user.role == 'editor' else 'published')
    try:
        db.session.add(item)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError('机构数据引用无效或与现有记录冲突') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('机构字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise
    return {'item': _admin_to_dict(item)}


def update_item_with_draft(model, DraftModel, item_id, data, user, fk_field):
    if model is not Agency:
        raise ValidationError('不支持的资源')
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    values = validate_agency_data(data, partial=True)
    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()

    if user.role not in ('admin', 'editor'):
        raise AuthenticationError('权限不足', http_status=403)

    if item.status == 'draft':
        for key, value in values.items():
            setattr(item, key, value)
    elif draft:
        snapshot = _business_snapshot(item, 'agencies')
        if draft.data:
            snapshot.update(_draft_payload('agencies', draft.data))
        snapshot.update(_json_safe_values(values))
        draft.data = snapshot
        draft.editor_id = user.id
    elif user.role == 'admin':
        for key, value in values.items():
            setattr(item, key, value)
    else:
        snapshot = _business_snapshot(item, 'agencies')
        snapshot.update(_json_safe_values(values))
        db.session.add(DraftModel(**{
            fk_field: item_id,
            'data': snapshot,
            'editor_id': user.id,
        }))

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError('机构数据引用无效或与现有记录冲突') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('机构字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise
    return get_item_with_draft(model, DraftModel, item_id, fk_field)


def approve_item(model, DraftModel, item_id, fk_field):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
    if item.status != 'draft' and not draft:
        raise ValidationError('该记录没有待审核修改')
    if draft:
        snapshot = _business_snapshot(item, 'agencies')
        snapshot.update(_draft_payload('agencies', draft.data))
        values = validate_agency_data(snapshot, partial=False)
        for key, value in values.items():
            setattr(item, key, value)
        db.session.delete(draft)
    item.status = 'published'
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError('机构数据引用无效或与现有记录冲突') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('机构字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise
    return {'item': _admin_to_dict(item)}


def batch_approve_items(model, DraftModel, ids, fk_field):
    approved = []
    try:
        for item_id in ids:
            item = db.session.get(model, item_id)
            if not item:
                raise NotFoundError(f'记录不存在: {item_id}')
            draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
            if item.status != 'draft' and not draft:
                raise ValidationError(f'记录没有待审核修改: {item_id}')
            if draft:
                snapshot = _business_snapshot(item, 'agencies')
                snapshot.update(_draft_payload('agencies', draft.data))
                values = validate_agency_data(snapshot, partial=False)
                for key, value in values.items():
                    setattr(item, key, value)
                db.session.delete(draft)
            item.status = 'published'
            approved.append(item_id)
        db.session.commit()
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('机构字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise
    return {'approved': approved, 'old_secure_map': {}}


def suspend_item(model, DraftModel, item_id, fk_field):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = DraftModel.query.filter_by(**{fk_field: item_id}).first()
    if draft:
        db.session.delete(draft)
    item.status = 'draft'
    db.session.commit()
    return {'item': _admin_to_dict(item)}


def delete_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    db.session.delete(item)
    db.session.commit()


def validate_agency_data(data, partial=False):
    values = _allowed_payload(data, EDITABLE_FIELDS['agencies'])
    values = normalize_model_strings(
        Agency, values, required=('name', 'scene_id'),
    )
    if not partial and not values.get('name'):
        raise ValidationError('name 不能为空')
    if not partial and not values.get('scene_id'):
        raise ValidationError('scene_id 不能为空')
    if 'name' in values and not values['name']:
        raise ValidationError('name 不能为空')
    if 'scene_id' in values and not db.session.get(AgencyScene, values['scene_id']):
        raise ValidationError('scene_id 不存在')
    if 'sort_order' in values:
        values['sort_order'] = _normalize_integer(
            values['sort_order'], 'sort_order',
        )
    return values


def validate_news_data(data, partial=False):
    values = _allowed_payload(data, EDITABLE_FIELDS['news'])
    values = normalize_model_strings(
        News, values, required=('type', 'title'),
    )
    if not partial:
        for required in ('type', 'title', 'date'):
            if values.get(required) in (None, ''):
                raise ValidationError(f'{required} 不能为空')
    if 'type' in values and values['type'] not in ('cooperation', 'hotspot', 'update'):
        raise ValidationError('无效的资讯类型')
    if 'risk_level' in values and values['risk_level'] not in (None, 'high', 'medium', 'low'):
        raise ValidationError('无效的风险等级')
    if 'update_type' in values and values['update_type'] not in (None, '修订', '新增', '废止'):
        raise ValidationError('无效的更新类型')
    if 'title' in values and not values['title']:
        raise ValidationError('title 不能为空')
    if 'date' in values:
        values['date'] = _parse_date(values['date'], 'date')
    if values.get('country_id') is not None and not db.session.get(Country, values['country_id']):
        raise ValidationError('country_id 不存在')
    return values


def validate_tag_ids(tag_ids):
    if not isinstance(tag_ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in tag_ids):
        raise ValidationError('tag_ids 必须为整数数组')
    tag_ids = list(dict.fromkeys(tag_ids))
    if tag_ids:
        found = {row[0] for row in NewsTag.query.with_entities(NewsTag.id).filter(NewsTag.id.in_(tag_ids)).all()}
        missing = set(tag_ids) - found
        if missing:
            raise ValidationError(f'tag_ids 包含不存在的标签: {sorted(missing)}')
    return tag_ids


def create_news(data, user):
    if user.role not in ('admin', 'editor'):
        raise AuthenticationError('权限不足', http_status=403)
    payload = dict(data)
    content = payload.pop('content', None)
    if content is not None:
        content = normalize_model_strings(
            NewsText, {'content': content},
        )['content']
    tag_ids = validate_tag_ids(payload.pop('tag_ids', []))
    values = validate_news_data(payload, partial=False)
    item = News(**values, status='draft' if user.role == 'editor' else 'published')
    try:
        db.session.add(item)
        db.session.flush()
        if content is not None:
            db.session.add(NewsText(news_id=item.id, content=content))
        _replace_news_tags(item.id, tag_ids)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError('资讯数据引用无效或与现有记录冲突') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('资讯字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise
    return item.id


def update_news(item_id, data, user):
    item = db.session.get(News, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    payload = dict(data)
    content_provided = 'content' in payload
    tags_provided = 'tag_ids' in payload
    content = payload.pop('content', None)
    if content_provided and content is not None:
        content = normalize_model_strings(
            NewsText, {'content': content},
        )['content']
    tag_ids = validate_tag_ids(payload.pop('tag_ids')) if tags_provided else None
    values = validate_news_data(payload, partial=True)
    draft = NewsDraft.query.filter_by(news_id=item_id).first()

    if user.role not in ('admin', 'editor'):
        raise AuthenticationError('权限不足', http_status=403)

    if item.status == 'draft':
        for key, value in values.items():
            setattr(item, key, value)
        if content_provided:
            _set_news_content(item_id, content)
        if tags_provided:
            _replace_news_tags(item_id, tag_ids)
    elif draft:
        snapshot = _news_snapshot(item)
        if draft.data:
            snapshot.update(_draft_payload('news', draft.data))
        snapshot.update(_json_safe_values(values))
        if content_provided:
            snapshot['content'] = content
        if tags_provided:
            snapshot['tag_ids'] = tag_ids
        draft.data = snapshot
        draft.editor_id = user.id
    elif user.role == 'admin':
        for key, value in values.items():
            setattr(item, key, value)
        if content_provided:
            _set_news_content(item_id, content)
        if tags_provided:
            _replace_news_tags(item_id, tag_ids)
    else:
        snapshot = _news_snapshot(item)
        snapshot.update(_json_safe_values(values))
        if content_provided:
            snapshot['content'] = content
        if tags_provided:
            snapshot['tag_ids'] = tag_ids
        db.session.add(NewsDraft(
            news_id=item_id,
            data=snapshot,
            editor_id=user.id,
        ))

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError('资讯数据引用无效或与现有记录冲突') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('资讯字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise


def approve_news(item_id, commit=True):
    item = db.session.get(News, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    draft = NewsDraft.query.filter_by(news_id=item_id).first()
    if item.status != 'draft' and not draft:
        raise ValidationError('该资讯没有待审核修改')
    if draft:
        snapshot = _news_snapshot(item)
        snapshot.update(_draft_payload('news', draft.data))
        content = snapshot.pop('content', None)
        if content is not None:
            content = normalize_model_strings(
                NewsText, {'content': content},
            )['content']
        tag_ids = validate_tag_ids(snapshot.pop('tag_ids', []))
        values = validate_news_data(snapshot, partial=False)
        for key, value in values.items():
            setattr(item, key, value)
        _set_news_content(item_id, content)
        _replace_news_tags(item_id, tag_ids)
        db.session.delete(draft)
    item.status = 'published'
    if commit:
        try:
            db.session.commit()
        except (DataError, StatementError) as exc:
            db.session.rollback()
            raise ValidationError('资讯字段类型或长度不合法') from exc
        except Exception:
            db.session.rollback()
            raise
    return item


def batch_approve_news(ids):
    try:
        for item_id in ids:
            approve_news(item_id, commit=False)
        db.session.commit()
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('资讯字段类型或长度不合法') from exc
    except Exception:
        db.session.rollback()
        raise
    return {'approved': ids}


def list_ref_items(model):
    return {'items': [_admin_to_dict(item) for item in model.query.order_by(model.id).all()]}


def get_ref_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    return {'item': _admin_to_dict(item)}


def create_ref_item(model, data):
    allowed = REF_CREATE_FIELDS.get(model.__tablename__)
    if allowed is None:
        raise ValidationError('不支持的资源')
    values = _allowed_payload(data, allowed)
    _validate_ref(model, values, partial=False)
    try:
        item = model(**values)
        db.session.add(item)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError('记录已存在或引用关系无效') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('参考数据字段类型或长度不合法') from exc
    return {'item': _admin_to_dict(item)}


def update_ref_item(model, item_id, data):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    allowed = REF_CREATE_FIELDS.get(model.__tablename__, set()) - {'id'}
    values = _allowed_payload(data, allowed)
    _validate_ref(model, values, partial=True)
    try:
        for key, value in values.items():
            setattr(item, key, value)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError('记录与现有数据冲突或引用关系无效') from exc
    except (DataError, StatementError) as exc:
        db.session.rollback()
        raise ValidationError('参考数据字段类型或长度不合法') from exc
    return {'item': _admin_to_dict(item)}


def delete_ref_item(model, item_id):
    item = db.session.get(model, item_id)
    if not item:
        raise NotFoundError('记录不存在')
    try:
        db.session.delete(item)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError('记录仍被其他数据引用，无法删除') from exc


def _validate_ref(model, values, partial):
    required = {
        Country: ('id', 'name_zh'), ComplianceScene: ('id', 'label_zh'),
        AgencyCategory: ('id', 'label_zh'), AgencyScene: ('id', 'category_id', 'label_zh'),
        NewsTag: ('name_zh',),
    }.get(model, ())
    values.update(normalize_model_strings(
        model, values, required=required,
    ))
    if not partial:
        for field in required:
            if values.get(field) in (None, ''):
                raise ValidationError(f'{field} 不能为空')
    if model is AgencyScene and 'category_id' in values and not db.session.get(AgencyCategory, values['category_id']):
        raise ValidationError('category_id 不存在')
    if 'sort_order' in values:
        values['sort_order'] = _normalize_integer(
            values['sort_order'], 'sort_order',
        )


def _allowed_payload(data, allowed):
    if not isinstance(data, dict):
        raise ValidationError('请求体必须为 JSON 对象')
    unknown = set(data) - allowed
    if unknown:
        raise ValidationError(f'不支持的字段: {", ".join(sorted(unknown))}')
    return {key: data[key] for key in allowed if key in data}


def _normalize_integer(value, field):
    if isinstance(value, bool):
        raise ValidationError(f'{field} 必须为整数')
    if isinstance(value, int):
        normalized = value
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lstrip('-').isdigit():
            normalized = int(stripped)
        else:
            raise ValidationError(f'{field} 必须为整数')
    else:
        raise ValidationError(f'{field} 必须为整数')
    if not -2_147_483_648 <= normalized <= 2_147_483_647:
        raise ValidationError(f'{field} 超出整数范围')
    return normalized


def _parse_date(value, field):
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValidationError(f'{field} 必须为 YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'{field} 必须为有效的 YYYY-MM-DD 日期') from exc


def _business_snapshot(item, resource):
    result = {}
    for field in EDITABLE_FIELDS[resource]:
        value = getattr(item, field)
        result[field] = value.isoformat() if hasattr(value, 'isoformat') else value
    return result


def _news_snapshot(item):
    snapshot = _business_snapshot(item, 'news')
    text = db.session.get(NewsText, item.id)
    snapshot['content'] = text.content if text else None
    snapshot['tag_ids'] = [row.tag_id for row in NewsTagRelation.query.filter_by(news_id=item.id).all()]
    return snapshot


def _json_safe_values(values):
    return {
        key: value.isoformat() if hasattr(value, 'isoformat') else value
        for key, value in values.items()
    }


def _draft_payload(resource, data):
    """Return only business fields allowed in a persisted Draft snapshot."""
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValidationError('草稿数据格式无效')
    allowed = set(EDITABLE_FIELDS[resource])
    if resource == 'news':
        allowed.update(('content', 'tag_ids'))
    return {key: data[key] for key in allowed if key in data}


def _set_news_content(news_id, content):
    text = db.session.get(NewsText, news_id)
    if content is None:
        if text:
            db.session.delete(text)
    elif text:
        text.content = content
    else:
        db.session.add(NewsText(news_id=news_id, content=content))


def _replace_news_tags(news_id, tag_ids):
    NewsTagRelation.query.filter_by(news_id=news_id).delete(synchronize_session=False)
    for tag_id in tag_ids:
        db.session.add(NewsTagRelation(news_id=news_id, tag_id=tag_id))


def _admin_to_dict(item, draft=None):
    result = {}
    for col in item.__table__.columns:
        value = getattr(item, col.name)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        result[col.name] = value
    result['has_draft'] = draft is not None
    result['review_status'] = 'pending' if (draft is not None or result.get('status') == 'draft') else 'none'
    return result


def _admin_to_dict_full(item):
    return {col.name: getattr(item, col.name) for col in item.__table__.columns}
