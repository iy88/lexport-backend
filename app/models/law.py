from app.extensions import bigint_pk_type, db


class ComplianceScene(db.Model):
    __tablename__ = 'compliance_scenes'

    id = db.Column(db.String(20), primary_key=True)
    label_zh = db.Column(db.String(30), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Law(db.Model):
    __tablename__ = 'laws'

    id = db.Column(bigint_pk_type(), primary_key=True, autoincrement=True)
    title_en = db.Column(db.String(300))
    title_cn = db.Column(db.String(300), nullable=False)
    law_number = db.Column(db.String(100))
    country_id = db.Column(db.String(10), db.ForeignKey('countries.id'), nullable=False)
    scene_id = db.Column(db.String(20), db.ForeignKey('compliance_scenes.id'), nullable=False)
    effective_date = db.Column(db.Date)
    summary = db.Column(db.Text)
    object_name = db.Column(db.String(500), unique=True, nullable=True)
    pending_file_name = db.Column(db.String(500))
    status = db.Column(db.Enum('draft', 'published', name='content_status_enum'), default='published', nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        db.Index('idx_laws_status_created', 'status', 'created_at'),
    )
