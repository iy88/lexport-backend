from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)


def bigint_pk_type():
    """Use BIGINT in production and SQLite's autoincrement-capable INTEGER in tests."""
    return db.BigInteger().with_variant(db.Integer(), 'sqlite')
