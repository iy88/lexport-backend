from app.extensions import db


class LawDraft(db.Model):
    __tablename__ = 'laws_drafts'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    law_id = db.Column(db.BigInteger, db.ForeignKey('laws.id', ondelete='CASCADE'), unique=True, nullable=False)
    data = db.Column(db.JSON, nullable=False)
    editor_id = db.Column(db.BigInteger, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )


class NewsDraft(db.Model):
    __tablename__ = 'news_drafts'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    news_id = db.Column(db.BigInteger, db.ForeignKey('news.id', ondelete='CASCADE'), unique=True, nullable=False)
    data = db.Column(db.JSON, nullable=False)
    editor_id = db.Column(db.BigInteger, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )


class AgencyDraft(db.Model):
    __tablename__ = 'agencies_drafts'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    agency_id = db.Column(db.BigInteger, db.ForeignKey('agencies.id', ondelete='CASCADE'), unique=True, nullable=False)
    data = db.Column(db.JSON, nullable=False)
    editor_id = db.Column(db.BigInteger, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )
