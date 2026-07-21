import pytest

from app import create_app
from app.extensions import db as _db
from app.models.country import Country
from app.models.draft import LawDraft
from app.models.law import ComplianceScene, Law
from app.models.user import User


@pytest.fixture
def app(tmp_path):
    """Create a test Flask app with in-memory SQLite."""
    a = create_app('testing', initialize_database=False)
    a.config['UPLOAD_PATH'] = str(tmp_path / 'uploads')
    with a.app_context():
        _db.create_all()
        # Seed lookup tables needed by FK constraints.
        _db.session.add(Country(id='ZA', name_zh='南非', name_en='South Africa', sort_order=1))
        _db.session.add(Country(id='NG', name_zh='尼日利亚', name_en='Nigeria', sort_order=2))
        _db.session.add(ComplianceScene(id='customs', label_zh='海关进出口', sort_order=1))
        _db.session.add(ComplianceScene(id='labor', label_zh='劳动用工', sort_order=2))
        _db.session.commit()
    yield a
    with a.app_context():
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_user_token(app, username, role):
    """Create a user and return ``(user, token)`` for role fixtures."""
    with app.app_context():
        u = User(username=username, password_hash='$2b$12$...', role=role)
        _db.session.add(u)
        _db.session.commit()
        from app.utils.jwt_utils import generate_access_token
        token = generate_access_token(u.id, u.role)
        return u, token


@pytest.fixture
def admin_user(app):
    return _make_user_token(app, 'admin_test', 'admin')


@pytest.fixture
def editor_user(app):
    return _make_user_token(app, 'editor_test', 'editor')


@pytest.fixture
def regular_user(app):
    return _make_user_token(app, 'user_test', 'user')
