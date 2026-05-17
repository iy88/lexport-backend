from app.extensions import db


class BudgetRange(db.Model):
    __tablename__ = 'budget_ranges'

    id = db.Column(db.String(20), primary_key=True)
    label_zh = db.Column(db.String(50), nullable=False)
    min_amount = db.Column(db.Integer)
    max_amount = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, default=0)
