from app.extensions import db


class ComplianceScene(db.Model):
    __tablename__ = 'compliance_scenes'

    id = db.Column(db.String(20), primary_key=True)
    label_zh = db.Column(db.String(30), nullable=False)
    icon_name = db.Column(db.String(30))
    sort_order = db.Column(db.Integer, default=0)


class Law(db.Model):
    __tablename__ = 'laws'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    title = db.Column(db.String(300), nullable=False)
    country_id = db.Column(db.String(10), db.ForeignKey('countries.id'), nullable=False)
    scene_id = db.Column(db.String(20), db.ForeignKey('compliance_scenes.id'), nullable=False)
    level = db.Column(db.String(30))
    penalty = db.Column(db.Text)
    effective_date = db.Column(db.Date)
    summary = db.Column(db.Text)
    full_text_url = db.Column(db.String(500))
    status = db.Column(db.Enum('draft', 'published', name='content_status_enum'), default='published', nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp(), nullable=False)
