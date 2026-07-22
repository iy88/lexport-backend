from unittest.mock import patch

import pytest

from app.models.agency import Agency, AgencyCategory, AgencyScene
from app.models.content import NewsText
from app.models.draft import AgencyDraft, NewsDraft
from app.models.news import News, NewsTag, NewsTagRelation
from app.models.user import User
from app.services import admin_service
from app.utils.errors import ConflictError, ValidationError


def _seed_content_refs(db):
    db.session.add(AgencyCategory(id='legal', label_zh='法律服务'))
    db.session.add(AgencyScene(
        id='legal-advice', category_id='legal', label_zh='法律咨询',
    ))
    tags = [NewsTag(name_zh='税务'), NewsTag(name_zh='劳动')]
    db.session.add_all(tags)
    db.session.commit()
    return tags


def _news_payload(title='原始标题', content='原始正文', tag_ids=None):
    return {
        'type': 'hotspot',
        'title': title,
        'date': '2026-07-01',
        'summary': '原始摘要',
        'content': content,
        'tag_ids': tag_ids or [],
    }


def test_editor_created_news_is_hidden_until_approved(
        app, db, client, editor_user, admin_user):
    with app.app_context():
        tags = _seed_content_refs(db)
        editor_token = editor_user[1]
        admin_token = admin_user[1]

        response = client.post(
            '/api/admin/news',
            json=_news_payload(tag_ids=[tags[0].id]),
            headers={'Authorization': f'Bearer {editor_token}'},
        )
        assert response.status_code == 201
        news_id = response.get_json()['data']['item']['id']
        assert db.session.get(News, news_id).status == 'draft'
        assert NewsDraft.query.filter_by(news_id=news_id).first() is None
        assert client.get(f'/api/news/{news_id}').status_code == 404

        pending = client.get(
            '/api/admin/news?review_status=pending',
            headers={'Authorization': f'Bearer {editor_token}'},
        ).get_json()['data']['items']
        assert [item['id'] for item in pending] == [news_id]

        approved = client.post(
            f'/api/admin/news/{news_id}/approve',
            headers={'Authorization': f'Bearer {admin_token}'},
        )
        assert approved.status_code == 200
        assert client.get(f'/api/news/{news_id}').status_code == 200


def test_published_news_draft_merges_editors_and_publishes_atomically(
        app, db, client, editor_user):
    with app.app_context():
        tags = _seed_content_refs(db)
        editor = db.session.get(User, editor_user[0].id)
        second_editor = User(
            username='editor_second', password_hash='unused', role='editor',
        )
        db.session.add(second_editor)
        db.session.commit()
        news_id = admin_service.create_news(
            _news_payload(tag_ids=[tags[0].id]),
            User(username='admin-shape', role='admin'),
        )

        admin_service.update_news(news_id, {
            'title': '编辑后的标题',
            'content': '编辑后的正文',
            'tag_ids': [tags[1].id],
        }, editor)
        admin_service.update_news(
            news_id, {'summary': '第二位编辑的摘要'}, second_editor,
        )

        live = db.session.get(News, news_id)
        draft = NewsDraft.query.filter_by(news_id=news_id).one()
        assert live.title == '原始标题'
        assert db.session.get(NewsText, news_id).content == '原始正文'
        assert draft.data['title'] == '编辑后的标题'
        assert draft.data['summary'] == '第二位编辑的摘要'
        assert draft.data['content'] == '编辑后的正文'
        assert draft.data['tag_ids'] == [tags[1].id]

        preview = client.get(
            f'/api/admin/news/{news_id}',
            headers={'Authorization': f'Bearer {editor_user[1]}'},
        )
        assert preview.status_code == 200
        preview_item = preview.get_json()['data']['item']
        assert preview_item['status'] == 'published'
        assert preview_item['has_draft'] is True
        assert preview_item['content'] == '编辑后的正文'
        assert [tag['id'] for tag in preview_item['tags']] == [tags[1].id]

        admin_service.approve_news(news_id)
        assert db.session.get(News, news_id).title == '编辑后的标题'
        assert db.session.get(News, news_id).summary == '第二位编辑的摘要'
        assert db.session.get(NewsText, news_id).content == '编辑后的正文'
        assert [row.tag_id for row in NewsTagRelation.query.filter_by(
            news_id=news_id,
        ).all()] == [tags[1].id]
        assert NewsDraft.query.filter_by(news_id=news_id).first() is None


def test_news_batch_approval_applies_content_and_tags(app, db, editor_user):
    with app.app_context():
        tags = _seed_content_refs(db)
        editor = db.session.get(User, editor_user[0].id)
        ids = []
        for suffix in ('一', '二'):
            news_id = admin_service.create_news(
                _news_payload(title=f'资讯{suffix}', tag_ids=[tags[0].id]),
                User(username=f'admin-{suffix}', role='admin'),
            )
            admin_service.update_news(news_id, {
                'content': f'新正文{suffix}', 'tag_ids': [tags[1].id],
            }, editor)
            ids.append(news_id)

        assert admin_service.batch_approve_news(ids) == {'approved': ids}
        for news_id, suffix in zip(ids, ('一', '二')):
            assert db.session.get(NewsText, news_id).content == f'新正文{suffix}'
            assert NewsTagRelation.query.filter_by(
                news_id=news_id, tag_id=tags[1].id,
            ).count() == 1
            assert NewsDraft.query.filter_by(news_id=news_id).first() is None


def test_admin_cannot_bypass_pending_agency_draft(app, db, editor_user):
    with app.app_context():
        _seed_content_refs(db)
        editor = db.session.get(User, editor_user[0].id)
        admin = User(username='admin-shape', role='admin')
        agency_id = admin_service.create_item(Agency, {
            'name': '原机构', 'scene_id': 'legal-advice',
        }, admin)['item']['id']

        admin_service.update_item_with_draft(
            Agency, AgencyDraft, agency_id, {'name': '待审核机构'}, editor,
            'agency_id',
        )
        with pytest.raises(ConflictError):
            admin_service.update_item_with_draft(
                Agency, AgencyDraft, agency_id, {'name': '管理员覆盖'}, admin,
                'agency_id',
            )


def test_editor_created_agency_main_draft_is_shared(app, db, editor_user):
    with app.app_context():
        _seed_content_refs(db)
        first_editor = db.session.get(User, editor_user[0].id)
        second_editor = User(username='agency_editor', role='editor')
        created = admin_service.create_item(Agency, {
            'name': '机构草稿', 'scene_id': 'legal-advice',
        }, first_editor)['item']

        assert created['status'] == 'draft'
        assert AgencyDraft.query.filter_by(agency_id=created['id']).first() is None
        admin_service.update_item_with_draft(
            Agency, AgencyDraft, created['id'], {'region': '南非'},
            second_editor, 'agency_id',
        )
        assert db.session.get(Agency, created['id']).region == '南非'
        approved = admin_service.approve_item(
            Agency, AgencyDraft, created['id'], 'agency_id',
        )
        assert approved['item']['status'] == 'published'


def test_news_approval_commit_failure_rolls_back_every_table(
        app, db, editor_user):
    with app.app_context():
        tags = _seed_content_refs(db)
        editor = db.session.get(User, editor_user[0].id)
        news_id = admin_service.create_news(
            _news_payload(tag_ids=[tags[0].id]),
            User(username='admin-shape', role='admin'),
        )
        admin_service.update_news(news_id, {
            'title': '不能发布的标题',
            'content': '不能发布的正文',
            'tag_ids': [tags[1].id],
        }, editor)

        with patch.object(db.session, 'commit', side_effect=RuntimeError('forced')):
            with pytest.raises(RuntimeError, match='forced'):
                admin_service.approve_news(news_id)

        db.session.expire_all()
        assert db.session.get(News, news_id).title == '原始标题'
        assert db.session.get(NewsText, news_id).content == '原始正文'
        assert NewsTagRelation.query.filter_by(
            news_id=news_id, tag_id=tags[0].id,
        ).count() == 1
        assert NewsDraft.query.filter_by(news_id=news_id).one()


def test_discard_news_draft_preserves_live_content(
        app, db, client, editor_user, admin_user):
    with app.app_context():
        tags = _seed_content_refs(db)
        editor = db.session.get(User, editor_user[0].id)
        news_id = admin_service.create_news(
            _news_payload(tag_ids=[tags[0].id]),
            User(username='admin-shape', role='admin'),
        )
        admin_service.update_news(news_id, {
            'content': '待丢弃正文', 'tag_ids': [tags[1].id],
        }, editor)

        response = client.delete(
            f'/api/admin/news/{news_id}/draft',
            headers={'Authorization': f'Bearer {admin_user[1]}'},
        )
        assert response.status_code == 200
        assert db.session.get(NewsText, news_id).content == '原始正文'
        assert NewsTagRelation.query.filter_by(
            news_id=news_id, tag_id=tags[0].id,
        ).count() == 1
        assert NewsDraft.query.filter_by(news_id=news_id).first() is None


@pytest.mark.parametrize('resource', ('news', 'agencies'))
def test_admin_lists_reject_invalid_review_status(app, db, resource):
    with app.app_context():
        model = News if resource == 'news' else Agency
        with pytest.raises(ValidationError):
            admin_service.list_items(
                model, resource, review_status='unexpected',
            )


def test_news_rejects_unknown_writable_fields(app, db):
    with app.app_context():
        _seed_content_refs(db)
        with pytest.raises(ValidationError):
            admin_service.validate_news_data({
                'type': 'hotspot', 'title': '标题',
                'date': '2026-07-01', 'id': 999,
            })
