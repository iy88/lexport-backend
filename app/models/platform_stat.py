from app.extensions import db


class PlatformStat(db.Model):
    __tablename__ = 'platform_stats'

    id = db.Column(db.String(20), primary_key=True)
    value = db.Column(db.String(20), nullable=False)
    label_zh = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
