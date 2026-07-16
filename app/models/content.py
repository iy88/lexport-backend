from app.extensions import db


class NewsText(db.Model):
    __tablename__ = 'news_text'

    news_id = db.Column(db.BigInteger, db.ForeignKey('news.id', ondelete='CASCADE'), primary_key=True)
    content = db.Column(db.Text(16_777_215), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )
