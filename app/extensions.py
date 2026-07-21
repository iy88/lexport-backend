from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
mail = Mail()


def bigint_pk_type():
    """Use BIGINT in production and SQLite's autoincrement-capable INTEGER in tests."""
    return db.BigInteger().with_variant(db.Integer(), 'sqlite')
