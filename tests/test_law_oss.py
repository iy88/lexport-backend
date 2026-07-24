"""Tests for law OSS migration: object names, CRUD, approve, suspend, delete, download."""

import io
import os
from functools import wraps
from unittest.mock import patch

import pytest
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.draft import LawDraft
from app.models.law import Law
from app.services.law_service import (
    _build_object_name,
    approve_law,
    batch_approve_laws,
    create_law,
    delete_law,
    discard_law_draft,
    get_law_with_draft,
    list_laws,
    suspend_law,
    update_law,
)
from app.utils.errors import AppError, ConflictError, NotFoundError, ValidationError


# ---------------------------------------------------------------------------
# Object name generation
# ---------------------------------------------------------------------------

class TestBuildObjectName:
    def test_chinese_only(self):
        name = _build_object_name('《南非海关管理法》', '', '.pdf')
        assert name == '《南非海关管理法》.pdf'

    def test_chinese_and_english(self):
        name = _build_object_name('《南非海关管理法》', 'South Africa Customs Act', '.PDF')
        assert name == '《南非海关管理法》-South Africa Customs Act.pdf'

    def test_empty_english_omitted(self):
        name = _build_object_name('《加纳劳动法》', '   ', '.pdf')
        assert name == '《加纳劳动法》.pdf'

    def test_unicode_normalization(self):
        name = _build_object_name('épreuve', '', '.pdf')  # e + combining acute → é
        assert name == 'épreuve.pdf'

    def test_slash_rejected(self):
        with pytest.raises(ValidationError, match='非法字符'):
            _build_object_name('test/pkg', '', '.pdf')

    def test_backslash_rejected(self):
        with pytest.raises(ValidationError, match='非法字符'):
            _build_object_name('test\\pkg', '', '.pdf')

    def test_no_extension_rejected(self):
        with pytest.raises(ValidationError, match='后缀名'):
            _build_object_name('test', '', '')

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError, match='标题不能为空'):
            _build_object_name('', '', '.pdf')

    def test_name_too_long(self):
        cn = '法' * 550
        with pytest.raises(ValidationError, match='过长'):
            _build_object_name(cn, '', '.pdf')


# ---------------------------------------------------------------------------
# OSS mock helper
# ---------------------------------------------------------------------------

def _mock_oss(func):
    """Decorator that mocks all OSS calls to prevent real network access."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        def fake_download(_object_name, local_path, **_kwargs):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as fh:
                fh.write(b'previous OSS content')

        with (
            patch('app.services.law_service.upload_file'),
            patch('app.services.law_service.delete_object'),
            patch('app.services.law_service.copy_object'),
            patch('app.services.law_service.download_file', side_effect=fake_download),
            patch('app.services.law_service.head_object'),
            patch('app.services.law_service.object_exists', return_value=False),
        ):
            return func(*args, **kwargs)

    return wrapper


def _file(content, filename):
    return FileStorage(stream=io.BytesIO(content), filename=filename)


# ---------------------------------------------------------------------------
# Admin create
# ---------------------------------------------------------------------------

class TestCreateLaw:
    @_mock_oss
    def test_admin_create_without_file(self, app, admin_user):
        _, token = admin_user
        data = {
            'title_cn': '测试法规',
            'country_id': 'ZA',
            'scene_id': 'customs',
        }
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            assert law['item']['status'] == 'published'
            assert law['item']['object_name'] is None
            assert law['item']['has_file'] is False

    @_mock_oss
    def test_admin_create_with_file(self, app, admin_user):
        _, token = admin_user
        file_storage = _file(b'dummy pdf content', 'test-law.pdf')
        data = {
            'title_cn': '《南非海关管理法》',
            'title_en': 'South Africa Customs Act',
            'country_id': 'ZA',
            'scene_id': 'customs',
        }
        with app.app_context():
            law = create_law(data, file_storage, admin_user[0])
            assert law['item']['status'] == 'published'
            assert law['item']['object_name'] == '《南非海关管理法》-South Africa Customs Act.pdf'
            assert law['item']['has_file'] is True

    @_mock_oss
    def test_editor_create_goes_to_draft(self, app, editor_user):
        file_storage = _file(b'dummy content', 'draft-law.pdf')
        data = {
            'title_cn': '编辑草稿法规',
            'country_id': 'ZA',
            'scene_id': 'customs',
        }
        with app.app_context():
            law = create_law(data, file_storage, editor_user[0])
            assert law['item']['status'] == 'draft'
            assert law['item']['object_name'] is None
            assert law['item']['has_file'] is True  # pending file
            row = db.session.get(Law, law['item']['id'])
            assert os.path.isfile(os.path.join(
                app.config['UPLOAD_PATH'], 'tmp', 'laws', row.pending_file_name,
            ))

    @_mock_oss
    def test_create_duplicate_object_name(self, app, admin_user):
        """Name collision with existing OSS object should return 409."""
        file_storage = _file(b'content', 'test.pdf')
        data = {'title_cn': '测试', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            # Simulate existing OSS object.
            with (
                patch('app.services.law_service.object_exists', return_value=True),
                patch('app.services.law_service.delete_object') as delete_mock,
            ):
                with pytest.raises(ConflictError, match='同名'):
                    create_law(data, file_storage, admin_user[0])
                delete_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Admin update
# ---------------------------------------------------------------------------

class TestUpdateLaw:
    @_mock_oss
    def test_admin_update_metadata_only(self, app, admin_user):
        data = {'title_cn': '原法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            result = update_law(lid, {'summary': '新增摘要'}, None, admin_user[0])
            assert result['item']['summary'] == '新增摘要'
            assert result['item']['status'] == 'published'

    @_mock_oss
    def test_admin_update_name_change_with_oss_copy(self, app, admin_user):
        file_storage = _file(b'content', 'old.pdf')
        data = {'title_cn': '旧名称', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, file_storage, admin_user[0])
            lid = law['item']['id']
            assert law['item']['object_name'] == '旧名称.pdf'
            result = update_law(lid, {'title_cn': '新名称'}, None, admin_user[0])
            assert result['item']['title_cn'] == '新名称'
            assert result['item']['object_name'] == '新名称.pdf'

    @_mock_oss
    def test_admin_replace_file_same_key(self, app, admin_user):
        file_storage = _file(b'v1', 'law.pdf')
        data = {'title_cn': '法规X', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, file_storage, admin_user[0])
            lid = law['item']['id']

            new_file = _file(b'v2', 'law.pdf')
            result = update_law(lid, {}, new_file, admin_user[0])
            assert result['item']['object_name'] == '法规X.pdf'

    @_mock_oss
    def test_admin_updates_existing_shared_draft(self, app, admin_user, editor_user):
        """Admin PUT should extend the shared draft without changing the live row."""
        data = {'title_cn': '共享草稿法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']

            update_law(lid, {'summary': 'editor change'}, None, editor_user[0])
            original_draft = LawDraft.query.filter_by(law_id=lid).one()
            original_draft_id = original_draft.id

            result = update_law(
                lid, {'law_number': 'ADMIN-001'}, None, admin_user[0],
            )

            assert result['item']['status'] == 'published'
            assert result['item']['has_draft'] is True
            assert result['item']['review_status'] == 'pending'
            assert result['item']['summary'] == 'editor change'
            assert result['item']['law_number'] == 'ADMIN-001'

            # The public/live version stays untouched until explicit approval.
            live = db.session.get(Law, lid)
            assert live.summary is None
            assert live.law_number is None

            shared_draft = LawDraft.query.filter_by(law_id=lid).one()
            assert shared_draft.id == original_draft_id
            assert shared_draft.data['summary'] == 'editor change'
            assert shared_draft.data['law_number'] == 'ADMIN-001'
            assert shared_draft.editor_id == admin_user[0].id

    @_mock_oss
    def test_admin_replaces_file_in_existing_shared_draft(
            self, app, admin_user, editor_user):
        data = {'title_cn': '共享文件法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, _file(b'published', 'published.pdf'), admin_user[0])
            lid = law['item']['id']
            live_object_name = law['item']['object_name']

            update_law(
                lid,
                {'summary': 'editor metadata'},
                _file(b'editor pending', 'editor.pdf'),
                editor_user[0],
            )
            original_draft = LawDraft.query.filter_by(law_id=lid).one()
            original_draft_id = original_draft.id
            old_pending = original_draft.pending_file_name
            old_path = os.path.join(
                app.config['UPLOAD_PATH'], 'tmp', 'laws', old_pending,
            )
            assert os.path.isfile(old_path)

            result = update_law(
                lid,
                {'title_cn': '管理员修订名称'},
                _file(b'admin pending', 'admin.PDF'),
                admin_user[0],
            )

            shared_draft = LawDraft.query.filter_by(law_id=lid).one()
            new_path = os.path.join(
                app.config['UPLOAD_PATH'], 'tmp', 'laws',
                shared_draft.pending_file_name,
            )
            assert shared_draft.id == original_draft_id
            assert shared_draft.pending_file_name != old_pending
            assert shared_draft.data['summary'] == 'editor metadata'
            assert shared_draft.data['title_cn'] == '管理员修订名称'
            assert shared_draft.editor_id == admin_user[0].id
            assert not os.path.exists(old_path)
            assert os.path.isfile(new_path)
            with open(new_path, 'rb') as pending_file:
                assert pending_file.read() == b'admin pending'

            live = db.session.get(Law, lid)
            assert live.title_cn == '共享文件法规'
            assert live.summary is None
            assert live.object_name == live_object_name
            assert result['item']['has_pending_file'] is True
            assert result['item']['pending_object_name'] == '管理员修订名称.pdf'

    @_mock_oss
    def test_editor_update_published_creates_draft(self, app, admin_user, editor_user):
        data = {'title_cn': '发布法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            result = update_law(lid, {'summary': 'editor建议修改'}, None, editor_user[0])
            assert result['item']['has_draft'] is True
            assert result['item']['review_status'] == 'pending'
            # Public law still returns original.
            pub = db.session.get(Law, lid)
            assert pub.summary is None  # unchanged


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

class TestApprove:
    @_mock_oss
    def test_approve_editor_created_main_draft(self, app, editor_user):
        file_storage = _file(b'new law', 'law.pdf')
        data = {'title_cn': '编辑新建法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, file_storage, editor_user[0])
            result = approve_law(law['item']['id'])
            assert result['item']['status'] == 'published'
            assert result['item']['object_name'] == '编辑新建法规.pdf'
            assert result['item']['has_pending_file'] is False

    @_mock_oss
    def test_approve_merges_draft(self, app, admin_user, editor_user):
        data = {'title_cn': '待审法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            update_law(lid, {'summary': '审核通过的内容'}, None, editor_user[0])

            result = approve_law(lid)
            assert result['item']['status'] == 'published'
            assert result['item']['summary'] == '审核通过的内容'
            assert result['item']['has_draft'] is False

    @_mock_oss
    def test_approve_without_draft_fails(self, app, admin_user):
        data = {'title_cn': '无草稿法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            with pytest.raises(AppError, match='没有待审核'):
                approve_law(lid)

    @_mock_oss
    def test_approve_with_pending_file(self, app, admin_user, editor_user):
        file_storage = _file(b'draft file content', 'draft.pdf')
        data = {'title_cn': '法规原文', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            # Editor updates with new file.
            update_law(lid, {'title_cn': '法规更新版'}, file_storage, editor_user[0])
            result = approve_law(lid)
            assert result['item']['object_name'] == '法规更新版.pdf'
            assert result['item']['status'] == 'published'


# ---------------------------------------------------------------------------
# Batch approve
# ---------------------------------------------------------------------------

class TestBatchApprove:
    @_mock_oss
    def test_per_item_independent(self, app, admin_user, editor_user):
        """One failure should not roll back previously approved items."""
        with app.app_context():
            l1 = create_law({'title_cn': 'A', 'country_id': 'ZA', 'scene_id': 'customs'},
                            None, admin_user[0])
            l2 = create_law({'title_cn': 'B', 'country_id': 'ZA', 'scene_id': 'customs'},
                            None, admin_user[0])
            l3 = create_law({'title_cn': 'C', 'country_id': 'ZA', 'scene_id': 'customs'},
                            None, admin_user[0])
            # Draft for l1, no draft for l2 (will fail), draft for l3.
            update_law(l1['item']['id'], {'summary': 'ok'}, None, editor_user[0])
            update_law(l3['item']['id'], {'summary': 'ok2'}, None, editor_user[0])

            result = batch_approve_laws([
                l1['item']['id'], l2['item']['id'], l3['item']['id'],
            ])
            assert l1['item']['id'] in result['approved']
            assert l3['item']['id'] in result['approved']
            assert len(result['failed']) == 1
            assert result['failed'][0]['id'] == l2['item']['id']


# ---------------------------------------------------------------------------
# Discard draft
# ---------------------------------------------------------------------------

class TestDiscardDraft:
    @_mock_oss
    def test_discard_keeps_published(self, app, admin_user, editor_user):
        data = {'title_cn': '已有法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            update_law(lid, {'summary': '待丢弃'}, None, editor_user[0])
            assert LawDraft.query.filter_by(law_id=lid).first() is not None

            result = discard_law_draft(lid)
            assert result['item']['has_draft'] is False
            assert LawDraft.query.filter_by(law_id=lid).first() is None

    @_mock_oss
    def test_discard_without_draft_fails(self, app, admin_user):
        data = {'title_cn': '无草稿', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            with pytest.raises(AppError, match='没有待审核'):
                discard_law_draft(law['item']['id'])


# ---------------------------------------------------------------------------
# Suspend
# ---------------------------------------------------------------------------

class TestSuspend:
    @_mock_oss
    def test_suspend_moves_oss_to_tmp(self, app, admin_user):
        """Suspend downloads OSS object, deletes from OSS, sets draft+pending_file."""
        file_storage = _file(b'oss content', 'law.pdf')
        data = {'title_cn': '可挂起法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, file_storage, admin_user[0])
            lid = law['item']['id']
            result = suspend_law(lid)
            assert result['item']['status'] == 'draft'
            assert result['item']['object_name'] is None
            assert result['item']['has_file'] is True  # pending file

    @_mock_oss
    def test_suspend_discards_existing_draft(self, app, admin_user, editor_user):
        data = {'title_cn': '有草稿的法规', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, None, admin_user[0])
            lid = law['item']['id']
            update_law(lid, {'summary': '草稿'}, None, editor_user[0])
            result = suspend_law(lid)
            assert result['item']['has_draft'] is False
            assert result['item']['status'] == 'draft'


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete:
    @_mock_oss
    def test_delete_draft(self, app, editor_user):
        file_storage = _file(b'draft content', 'test.pdf')
        data = {'title_cn': '待删草稿', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, file_storage, editor_user[0])
            lid = law['item']['id']
            delete_law(lid)
            assert db.session.get(Law, lid) is None

    @_mock_oss
    def test_delete_published_downloads_rollback(self, app, admin_user):
        file_storage = _file(b'published content', 'pub.pdf')
        data = {'title_cn': '待删已发布', 'country_id': 'ZA', 'scene_id': 'customs'}
        with app.app_context():
            law = create_law(data, file_storage, admin_user[0])
            lid = law['item']['id']
            delete_law(lid)
            assert db.session.get(Law, lid) is None

    def test_delete_missing_law(self, app):
        with app.app_context():
            with pytest.raises(NotFoundError, match='不存在'):
                delete_law(99999)


# ---------------------------------------------------------------------------
# Admin list / detail
# ---------------------------------------------------------------------------

class TestAdminListDetail:
    def test_list_default(self, app, admin_user):
        with app.app_context():
            create_law({'title_cn': 'A', 'country_id': 'ZA', 'scene_id': 'customs'},
                       None, admin_user[0])
            create_law({'title_cn': 'B', 'country_id': 'ZA', 'scene_id': 'customs'},
                       None, admin_user[0])
            result = list_laws()
            assert result['meta']['total'] == 2

    def test_list_filter_status(self, app, admin_user, editor_user):
        with app.app_context():
            create_law({'title_cn': 'Pub', 'country_id': 'ZA', 'scene_id': 'customs'},
                       None, admin_user[0])
            create_law({'title_cn': 'Draft', 'country_id': 'ZA', 'scene_id': 'customs'},
                       None, editor_user[0])
            result = list_laws(status='draft')
            assert result['meta']['total'] == 1
            assert result['items'][0]['title_cn'] == 'Draft'
            assert result['items'][0]['review_status'] == 'pending'

    def test_list_filter_review_status(self, app, admin_user, editor_user):
        with app.app_context():
            law = create_law({'title_cn': 'Pub', 'country_id': 'ZA', 'scene_id': 'customs'},
                             None, admin_user[0])
            update_law(law['item']['id'], {'summary': 'x'}, None, editor_user[0])
            result = list_laws(review_status='pending')
            assert result['meta']['total'] == 1

    def test_list_filter_keyword(self, app, admin_user):
        with app.app_context():
            create_law({
                'title_cn': '南非测试法规',
                'title_en': 'Unique Smoke Act',
                'law_number': 'ZA-SMOKE-001',
                'country_id': 'ZA',
                'scene_id': 'customs',
            }, None, admin_user[0])
            create_law({
                'title_cn': '尼日利亚其他法规',
                'country_id': 'NG',
                'scene_id': 'labor',
            }, None, admin_user[0])

            result = list_laws(filters={'keyword': 'SMOKE-001'})

            assert result['meta']['total'] == 1
            assert result['items'][0]['title_cn'] == '南非测试法规'

    def test_get_with_draft_preview(self, app, admin_user, editor_user):
        with app.app_context():
            law = create_law({'title_cn': 'Preview', 'country_id': 'ZA', 'scene_id': 'customs'},
                             None, admin_user[0])
            lid = law['item']['id']
            update_law(lid, {'summary': 'previewed'}, None, editor_user[0])
            result = get_law_with_draft(lid)
            assert result['item']['summary'] == 'previewed'
            assert result['item']['has_draft'] is True


# ---------------------------------------------------------------------------
# Public download
# ---------------------------------------------------------------------------

class TestPublicDownload:
    def test_download_redirects_302(self, client, app, admin_user):
        with app.app_context():
            data = {'title_cn': '下载测试', 'country_id': 'ZA', 'scene_id': 'customs'}
            file_storage = _file(b'download content', 'dl.pdf')
            with patch('app.services.law_service.object_exists', return_value=False):
                with patch('app.services.law_service.upload_file'):
                    create_law(data, file_storage, admin_user[0])

        with (
            patch('app.routes.law.head_object'),
            patch(
                'app.routes.law.generate_signed_url',
                return_value='https://oss.example.com/signed',
            ),
        ):
            resp = client.get('/api/laws/1/download')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('https://')

    def test_download_missing_law_404(self, client, app):
        resp = client.get('/api/laws/99999/download')
        assert resp.status_code == 404

    def test_download_no_file_404(self, client, app, admin_user):
        with app.app_context():
            with patch('app.services.law_service.object_exists', return_value=False):
                data = {'title_cn': '无文件法规', 'country_id': 'ZA', 'scene_id': 'customs'}
                create_law(data, None, admin_user[0])

        resp = client.get('/api/laws/1/download')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Serialization fields
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_admin_response_has_new_fields(self, app, admin_user):
        with app.app_context():
            law = create_law({'title_cn': '字段测试', 'country_id': 'ZA', 'scene_id': 'customs'},
                             None, admin_user[0])
            item = law['item']
            assert 'object_name' in item
            assert 'has_file' in item
            assert 'has_draft' in item
            assert 'review_status' in item
            assert 'has_pending_file' in item
            assert 'pending_object_name' in item
            assert 'filename' not in item
            assert 'secure_name' not in item
            assert 'pending_file_name' not in item

    def test_public_response_has_new_fields(self, app, admin_user):
        with app.app_context():
            file_storage = _file(b'content', 'pub.pdf')
            data = {'title_cn': '公开法规', 'country_id': 'ZA', 'scene_id': 'customs'}
            with patch('app.services.law_service.object_exists', return_value=False):
                with patch('app.services.law_service.upload_file'):
                    create_law(data, file_storage, admin_user[0])

        resp = app.test_client().get('/api/laws/1')
        assert resp.status_code == 200
        law = resp.get_json()['data']
        assert law['has_file'] is True
        assert 'filename' not in law
        assert 'secure_name' not in law
