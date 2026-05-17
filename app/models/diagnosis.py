from app.extensions import db


class DiagnosisRecord(db.Model):
    __tablename__ = 'diagnosis_records'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=True)
    country_id = db.Column(db.String(10), db.ForeignKey('countries.id'))
    size_id = db.Column(db.String(20), db.ForeignKey('company_sizes.id'))
    budget_id = db.Column(db.String(20), db.ForeignKey('budget_ranges.id'))
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)


class DiagnosisRecordScene(db.Model):
    __tablename__ = 'diagnosis_record_scenes'

    record_id = db.Column(db.BigInteger, db.ForeignKey('diagnosis_records.id'), primary_key=True)
    scene_id = db.Column(db.String(20), db.ForeignKey('compliance_scenes.id'), primary_key=True)


class DiagnosisRecordLaw(db.Model):
    __tablename__ = 'diagnosis_record_laws'

    record_id = db.Column(db.BigInteger, db.ForeignKey('diagnosis_records.id'), primary_key=True)
    law_id = db.Column(db.BigInteger, db.ForeignKey('laws.id'), primary_key=True)
