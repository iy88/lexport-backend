from app.extensions import db


class CompanySize(db.Model):
    __tablename__ = 'company_sizes'

    id = db.Column(db.String(20), primary_key=True)
    label_zh = db.Column(db.String(50), nullable=False)
    min_employees = db.Column(db.Integer)
    max_employees = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, default=0)
