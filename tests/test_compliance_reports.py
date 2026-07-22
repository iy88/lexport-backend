import io
import os
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from werkzeug.datastructures import FileStorage, MultiDict

from app.extensions import db
from app.models.diagnosis import DiagnosisRecord
from app.models.user import User
from app.services import compliance_service
from app.utils.errors import AppError, ValidationError
from app.utils.jwt_utils import generate_access_token


FORM = {
    'query': '请分析合规要求',
    'company_name': '测试企业',
    'industry': '制造业',
    'company_size': '中型',
    'target_country': '南非',
    'business_model': '独资',
    'budget_range': '100-500万',
}


def _verified_user():
    user = User(
        username=f'report_{uuid.uuid4().hex[:10]}',
        email=f'{uuid.uuid4().hex}@example.com',
        email_verified=True,
    )
    user.set_password('Example123')
    db.session.add(user)
    db.session.commit()
    return user


def _file(name='context.txt', content=b'valid utf-8 text'):
    return FileStorage(stream=io.BytesIO(content), filename=name)


def _client_response(status='in_progress'):
    response = SimpleNamespace(id=f'resp_{uuid.uuid4().hex}', status=status)
    client = Mock()
    client.responses.create.return_value = response
    return client


def _configure_report(app):
    app.config.update(
        REPORT_GENERATOR_APPID='test-app',
        BAILIAN_API_KEY='test-key',
        REPORT_AI_VERSION='test-ai',
        REPORT_DATA_CUTOFF_DATE='2026-01-01',
    )


def test_unverified_user_is_rejected_before_file_or_external_work(app):
    with app.app_context():
        user = User(username='unverified', email='u@example.com', email_verified=False)
        user.set_password('Example123')
        db.session.add(user)
        db.session.commit()

        with patch.object(compliance_service, '_save_tmp_file') as save_file:
            with pytest.raises(AppError) as exc_info:
                compliance_service.create_report(
                    user, FORM, MultiDict([('documents', _file())]), str(uuid.uuid4())
                )
        assert exc_info.value.code == 'EMAIL_VERIFICATION_REQUIRED'
        save_file.assert_not_called()


def test_file_signature_mismatch_does_not_reserve_record(app):
    _configure_report(app)
    with app.app_context(), patch.object(
        compliance_service, '_get_bailian_client', return_value=_client_response()
    ):
        user = _verified_user()
        with pytest.raises(ValidationError, match='PDF'):
            compliance_service.create_report(
                user,
                FORM,
                MultiDict([('documents', _file('fake.pdf', b'not a pdf'))]),
                str(uuid.uuid4()),
            )
        assert DiagnosisRecord.query.count() == 0
        tmp_dir = os.path.join(app.config['UPLOAD_PATH'], 'tmp')
        assert not os.path.isdir(tmp_dir) or not os.listdir(tmp_dir)


def test_same_key_same_payload_replays_without_external_work(app):
    _configure_report(app)
    client = _client_response()
    idem_key = str(uuid.uuid4())
    with (
        app.app_context(),
        patch.object(compliance_service, '_get_bailian_client', return_value=client),
        patch.object(compliance_service, 'upload_file') as upload,
        patch.object(compliance_service, 'generate_signed_url', return_value='https://signed'),
    ):
        user = _verified_user()
        first, replayed = compliance_service.create_report(
            user, FORM, MultiDict([('documents', _file())]), idem_key
        )
        second, replayed_again = compliance_service.create_report(
            user, FORM, MultiDict([('documents', _file())]), idem_key
        )

        assert replayed is False
        assert replayed_again is True
        assert first.id == second.id
        assert DiagnosisRecord.query.count() == 1
        assert upload.call_count == 1
        assert client.responses.create.call_count == 1


def test_same_key_different_payload_conflicts(app):
    _configure_report(app)
    client = _client_response()
    idem_key = str(uuid.uuid4())
    with (
        app.app_context(),
        patch.object(compliance_service, '_get_bailian_client', return_value=client),
        patch.object(compliance_service, 'upload_file'),
        patch.object(compliance_service, 'generate_signed_url', return_value='https://signed'),
    ):
        user = _verified_user()
        compliance_service.create_report(user, FORM, MultiDict(), idem_key)
        changed = dict(FORM, company_name='另一家公司')
        with pytest.raises(AppError) as exc_info:
            compliance_service.create_report(user, changed, MultiDict(), idem_key)
        assert exc_info.value.code == 'IDEMPOTENCY_CONFLICT'
        assert client.responses.create.call_count == 1


def test_partial_upload_is_compensated_and_record_failed(app):
    _configure_report(app)
    with (
        app.app_context(),
        patch.object(compliance_service, '_get_bailian_client', return_value=_client_response()),
        patch.object(
            compliance_service,
            'upload_file',
            side_effect=[None, AppError('OSS_ERROR', 'failed', 502)],
        ),
        patch.object(compliance_service, 'delete_object') as delete_object,
    ):
        user = _verified_user()
        with pytest.raises(AppError) as exc_info:
            compliance_service.create_report(
                user,
                FORM,
                MultiDict([
                    ('documents', _file('one.txt', b'one')),
                    ('documents', _file('two.txt', b'two')),
                ]),
                str(uuid.uuid4()),
            )
        assert exc_info.value.code == 'OSS_UPLOAD_FAILED'
        record = DiagnosisRecord.query.one()
        assert record.status == 'failed'
        delete_object.assert_called_once()


def test_terminal_replay_returns_200(app, client):
    _configure_report(app)
    with app.app_context():
        user = _verified_user()
        token = generate_access_token(user.id, user.role)
        idem_key = str(uuid.uuid4())
        fingerprint = compliance_service._compute_fingerprint(FORM, [])
        record = DiagnosisRecord(
            user_id=user.id,
            country='南非',
            company_size='中型',
            budget_range='100-500万',
            business_model='独资',
            status='failed',
            idempotency_key=idem_key,
            request_fingerprint=fingerprint,
            param={
                'input': FORM['query'],
                'biz_params': {
                    'company_name': FORM['company_name'],
                    'industry': FORM['industry'],
                    'documents': [],
                },
            },
        )
        db.session.add(record)
        db.session.commit()

    with patch.object(
        compliance_service, '_get_bailian_client', return_value=_client_response()
    ):
        response = client.post(
            '/api/compliance-reports',
            data=FORM,
            headers={
                'Authorization': f'Bearer {token}',
                'Idempotency-Key': idem_key,
            },
        )
    assert response.status_code == 200
    assert response.get_json()['data']['status'] == 'failed'
