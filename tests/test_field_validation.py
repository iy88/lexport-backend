from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.exc import StatementError

from app.extensions import db
from app.models.agency import AgencyCategory, AgencyScene
from app.models.news import NewsTag
from app.services import admin_service
from app.services.law_service import _validate_law_data
from app.utils.errors import ValidationError


def _seed_agency_scene():
    db.session.add(AgencyCategory(id='legal', label_zh='法律服务'))
    db.session.add(AgencyScene(
        id='legal-advice', category_id='legal', label_zh='法律咨询',
    ))
    db.session.commit()


def test_agency_strings_are_trimmed_typed_and_length_checked(app):
    with app.app_context():
        _seed_agency_scene()
        values = admin_service.validate_agency_data({
            'name': '  测试机构  ',
            'scene_id': ' legal-advice ',
            'region': ' 南非 ',
        })
        assert values['name'] == '测试机构'
        assert values['scene_id'] == 'legal-advice'
        assert values['region'] == '南非'

        with pytest.raises(ValidationError, match='200'):
            admin_service.validate_agency_data({
                'name': '机' * 201, 'scene_id': 'legal-advice',
            })
        with pytest.raises(ValidationError, match='phone 必须为字符串'):
            admin_service.validate_agency_data({'phone': 123}, partial=True)
        with pytest.raises(ValidationError, match='sort_order 必须为整数'):
            admin_service.validate_agency_data(
                {'sort_order': 1.5}, partial=True,
            )


def test_news_strings_are_trimmed_typed_and_length_checked(app):
    with app.app_context():
        values = admin_service.validate_news_data({
            'type': ' hotspot ',
            'title': '  合规资讯  ',
            'date': '2026-07-23',
            'source': ' 来源 ',
        })
        assert values['type'] == 'hotspot'
        assert values['title'] == '合规资讯'
        assert values['source'] == '来源'
        assert values['date'] == date(2026, 7, 23)

        with pytest.raises(ValidationError, match='300'):
            admin_service.validate_news_data({
                'type': 'hotspot', 'title': '资' * 301,
                'date': '2026-07-23',
            })
        with pytest.raises(ValidationError, match='summary 必须为字符串'):
            admin_service.validate_news_data({'summary': 1}, partial=True)


def test_reference_strings_follow_model_lengths(app):
    with app.app_context():
        values = {'name_zh': '  税务合规  '}
        admin_service._validate_ref(NewsTag, values, partial=False)
        assert values['name_zh'] == '税务合规'

        with pytest.raises(ValidationError, match='30'):
            admin_service.create_ref_item(NewsTag, {'name_zh': '标' * 31})
        with pytest.raises(ValidationError, match='label_zh 必须为字符串'):
            admin_service._validate_ref(
                AgencyCategory,
                {'id': 'category', 'label_zh': 123},
                partial=False,
            )


def test_law_fields_are_validated_before_persistence(app):
    with app.app_context():
        values = _validate_law_data({
            'title_cn': '  测试法规  ',
            'title_en': ' Test Law ',
            'law_number': ' No. 1 ',
            'country_id': ' ZA ',
            'scene_id': ' customs ',
            'effective_date': '2026-07-23',
        })
        assert values['title_cn'] == '测试法规'
        assert values['title_en'] == 'Test Law'
        assert values['law_number'] == 'No. 1'
        assert values['country_id'] == 'ZA'
        assert values['scene_id'] == 'customs'
        assert values['effective_date'] == date(2026, 7, 23)

        with pytest.raises(ValidationError, match='300'):
            _validate_law_data({
                'title_cn': '法' * 301,
                'country_id': 'ZA',
                'scene_id': 'customs',
            })
        with pytest.raises(ValidationError, match='law_number 必须为字符串'):
            _validate_law_data({'law_number': 123}, partial=True)


def test_statement_error_uses_standard_400_envelope(app, client, admin_user):
    error = StatementError('invalid value', None, None, ValueError('bad'))
    with patch.object(admin_service, 'create_news', side_effect=error):
        response = client.post(
            '/api/admin/news',
            json={
                'type': 'hotspot', 'title': '测试', 'date': '2026-07-23',
            },
            headers={'Authorization': f'Bearer {admin_user[1]}'},
        )
    assert response.status_code == 400
    assert response.get_json() == {
        'success': False,
        'error': {
            'code': 'VALIDATION_ERROR',
            'message': '字段类型或长度不合法',
        },
    }
