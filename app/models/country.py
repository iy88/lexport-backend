from app.extensions import db


class Country(db.Model):
    __tablename__ = 'countries'

    id = db.Column(db.String(10), primary_key=True)
    name_zh = db.Column(db.String(50), nullable=False)
    name_en = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, default=0)
