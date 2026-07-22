import re
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest

from app.extensions import db
from app.models.user import User
from app.utils.jwt_utils import generate_access_token, generate_verification_token


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def _user(username, email=None, verified=False, role='user'):
    user = User(
        username=username,
        email=email,
        email_verified=verified,
        role=role,
    )
    user.set_password('Example123')
    db.session.add(user)
    db.session.commit()
    return user


def _concrete_admin_path(rule):
    path = str(rule)
    replacements = {
        'item_id': '1',
        'user_id': '1',
        'report_id': '1',
        'resource': 'countries',
    }
    for _, name in re.findall(r'<(?:(int|string):)?([^>]+)>', path):
        path = re.sub(
            rf'<(?:(?:int|string):)?{re.escape(name)}>',
            replacements.get(name, '1'),
            path,
            count=1,
        )
    return path


def test_regular_user_is_denied_by_every_admin_route(app, client, regular_user):
    _, token = regular_user
    routes = [rule for rule in app.url_map.iter_rules() if str(rule).startswith('/api/admin')]
    assert routes
    for rule in routes:
        method = next(
            method for method in ('GET', 'POST', 'PUT', 'DELETE')
            if method in rule.methods
        )
        response = client.open(
            _concrete_admin_path(rule),
            method=method,
            headers=_auth(token),
            json={'ids': [1], 'role': 'editor'},
        )
        assert response.status_code == 403, f'{method} {rule}'


def test_database_role_overrides_jwt_claim(app, client):
    with app.app_context():
        user = _user('db_role_user')
        token = generate_access_token(user.id, 'admin')
    response = client.get('/api/admin/users', headers=_auth(token))
    assert response.status_code == 403


def test_noncanonical_subject_returns_401(app, client):
    with app.app_context():
        user = _user('subject_user')
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                'sub': f'+{user.id}',
                'type': 'access',
                'iat': now,
                'exp': now + timedelta(minutes=5),
            },
            app.config['JWT_SECRET_KEY'],
            algorithm='HS256',
        )
    response = client.get('/api/user/profile', headers=_auth(token))
    assert response.status_code == 401


def test_expired_and_malformed_access_tokens_return_401(app, client):
    with app.app_context():
        user = _user('expired_user')
        now = datetime.now(timezone.utc)
        expired = jwt.encode(
            {
                'sub': str(user.id), 'type': 'access',
                'iat': now - timedelta(hours=2),
                'exp': now - timedelta(hours=1),
            },
            app.config['JWT_SECRET_KEY'],
            algorithm='HS256',
        )
    assert client.get('/api/user/profile', headers=_auth(expired)).status_code == 401
    assert client.get(
        '/api/user/profile', headers=_auth('not-a-jwt'),
    ).status_code == 401


def test_registration_requires_email_and_survives_smtp_failure(app, client):
    missing = client.post(
        '/api/auth/register',
        json={'username': 'no_email', 'password': 'Example123'},
    )
    assert missing.status_code == 400

    with patch('app.services.auth_service.mail.send', side_effect=RuntimeError('smtp down')):
        response = client.post(
            '/api/auth/register',
            json={
                'username': 'smtp_failure',
                'password': 'Example123',
                'email': 'smtp-failure@example.com',
            },
        )
    assert response.status_code == 201
    assert response.get_json()['data']['verification_email_sent'] is False
    with app.app_context():
        assert User.query.filter_by(username='smtp_failure').one().email


def test_sixth_registration_is_rate_limited(app, client):
    with patch('app.services.auth_service.mail.send'):
        responses = [client.post(
            '/api/auth/register',
            json={
                'username': f'rate_user_{index}',
                'password': 'Example123',
                'email': f'rate-{index}@example.com',
            },
        ) for index in range(6)]
    assert [response.status_code for response in responses[:5]] == [201] * 5
    assert responses[5].status_code == 429
    assert responses[5].get_json()['error']['code'] == 'RATE_LIMITED'


def test_login_is_not_rate_limited(app, client):
    with app.app_context():
        _user('unlimited_login')
    responses = [client.post(
        '/api/auth/login',
        json={'login_id': 'unlimited_login', 'password': 'wrong-password'},
    ) for _ in range(10)]
    assert all(response.status_code == 401 for response in responses)


def test_email_actions_share_one_rate_limit(app, client):
    with app.app_context():
        user = _user('email_limit', 'email-limit@example.com')
        token = generate_access_token(user.id, user.role)

    with patch('app.services.user_service._try_send_verification', return_value=True):
        for _ in range(5):
            response = client.post(
                '/api/user/email/resend-verification', headers=_auth(token)
            )
            assert response.status_code == 200
        response = client.put(
            '/api/user/email',
            headers=_auth(token),
            json={'email': 'new-limit@example.com', 'password': 'Example123'},
        )
    assert response.status_code == 429
    assert response.get_json()['error']['code'] == 'RATE_LIMITED'


def test_changing_email_invalidates_old_verification_token(app, client):
    with app.app_context():
        user = _user('email_change', 'old@example.com')
        token = generate_access_token(user.id, user.role)
        old_verification = generate_verification_token(user.id, user.email)

    with patch('app.services.user_service._try_send_verification', return_value=True):
        changed = client.put(
            '/api/user/email',
            headers=_auth(token),
            json={'email': 'new@example.com', 'password': 'Example123'},
        )
    assert changed.status_code == 200
    rejected = client.post(
        '/api/auth/verify-email', json={'token': old_verification}
    )
    assert rejected.status_code == 400


def _report_stub(role):
    return SimpleNamespace(
        id=1,
        task_id='task-stub',
        status='in_progress',
        user_id=1,
        country='南非',
        company_size='中型',
        budget_range='100-500万',
        business_model='独资',
        idempotency_key=None,
        param={'input': '测试', 'biz_params': {'documents': []}},
        deleted=False,
        created_at=None,
        role=role,
    )


@pytest.mark.parametrize('role', ('user', 'editor'))
def test_sixth_report_request_is_rate_limited(app, client, role):
    with app.app_context():
        user = _user(
            f'report_limit_{role}', f'report-{role}@example.com',
            verified=True, role=role,
        )
        token = generate_access_token(user.id, user.role)
    stub = _report_stub(role)
    with patch(
        'app.services.compliance_service.create_report',
        return_value=(stub, False),
    ):
        responses = [client.post(
            '/api/compliance-reports',
            data={},
            headers={
                **_auth(token),
                'Idempotency-Key': str(uuid.uuid4()),
            },
        ) for _ in range(6)]
    assert [response.status_code for response in responses[:5]] == [202] * 5
    assert responses[5].status_code == 429


def test_admin_is_exempt_from_report_rate_limit(app, client):
    with app.app_context():
        admin = _user(
            'report_limit_admin', 'report-admin@example.com',
            verified=True, role='admin',
        )
        token = generate_access_token(admin.id, admin.role)
    stub = _report_stub('admin')
    with patch(
        'app.services.compliance_service.create_report',
        return_value=(stub, False),
    ):
        responses = [client.post(
            '/api/compliance-reports',
            data={},
            headers={
                **_auth(token),
                'Idempotency-Key': str(uuid.uuid4()),
            },
        ) for _ in range(7)]
    assert all(response.status_code == 202 for response in responses)
