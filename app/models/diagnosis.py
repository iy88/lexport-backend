from app.extensions import bigint_pk_type, db


class DiagnosisRecord(db.Model):
    __tablename__ = 'diagnosis_records'

    id = db.Column(bigint_pk_type(), primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=True)
    country = db.Column(db.String(30))
    company_size = db.Column(db.String(20))
    budget_range = db.Column(db.String(20))
    business_model = db.Column(db.String(20))
    task_id = db.Column(db.String(100), unique=True, index=True, nullable=True)
    status = db.Column(db.String(30), index=True)
    param = db.Column(db.JSON, nullable=False)
    idempotency_key = db.Column(db.String(64), nullable=True)
    request_fingerprint = db.Column(db.CHAR(64), nullable=True)
    deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
        index=True,
    )
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'idempotency_key', name='uq_diagnosis_user_idempotency'),
        db.Index('idx_diagnosis_user_deleted_created', 'user_id', 'deleted', 'created_at'),
    )


class DiagnosisResult(db.Model):
    __tablename__ = 'diagnosis_results'

    record_id = db.Column(db.BigInteger, db.ForeignKey('diagnosis_records.id', ondelete='CASCADE'), primary_key=True)
    result = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        nullable=False,
    )
