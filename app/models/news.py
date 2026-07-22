from app.extensions import bigint_pk_type, db


class News(db.Model):
    __tablename__ = 'news'

    id = db.Column(bigint_pk_type(), primary_key=True, autoincrement=True)
    type = db.Column(db.Enum('cooperation', 'hotspot', 'update', name='news_type_enum'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    source = db.Column(db.String(200))
    country_id = db.Column(db.String(10), db.ForeignKey('countries.id'))
    date = db.Column(db.Date, nullable=False)
    summary = db.Column(db.Text)
    risk_level = db.Column(db.Enum('high', 'medium', 'low', name='news_risk_enum'))
    involved_laws = db.Column(db.Text)
    response = db.Column(db.Text)
    update_type = db.Column(db.Enum('修订', '新增', '废止', name='news_update_type_enum'))
    change_desc = db.Column(db.Text)
    impact = db.Column(db.Text)
    advice = db.Column(db.Text)
    status = db.Column(db.Enum('draft', 'published', name='content_status_enum'), default='published', nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        db.Index('idx_news_status_date', 'status', 'date'),
    )


class NewsTag(db.Model):
    __tablename__ = 'news_tags'

    id = db.Column(bigint_pk_type(), primary_key=True, autoincrement=True)
    name_zh = db.Column(db.String(30), nullable=False, unique=True)


class NewsTagRelation(db.Model):
    __tablename__ = 'news_tag_relations'

    news_id = db.Column(db.BigInteger, db.ForeignKey('news.id', ondelete='CASCADE'), primary_key=True)
    tag_id = db.Column(db.BigInteger, db.ForeignKey('news_tags.id'), primary_key=True)
