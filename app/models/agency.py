from app.extensions import db


class AgencyCategory(db.Model):
    __tablename__ = 'agency_categories'

    id = db.Column(db.String(20), primary_key=True)
    label_zh = db.Column(db.String(50), nullable=False)
    icon_name = db.Column(db.String(30))
    sort_order = db.Column(db.Integer, default=0)


class AgencyScene(db.Model):
    __tablename__ = 'agency_scenes'

    id = db.Column(db.String(30), primary_key=True)
    category_id = db.Column(db.String(20), db.ForeignKey('agency_categories.id'), nullable=False)
    label_zh = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Agency(db.Model):
    __tablename__ = 'agencies'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name_zh = db.Column(db.String(200), nullable=False)
    scene_id = db.Column(db.String(30), db.ForeignKey('agency_scenes.id'), nullable=False)
    region = db.Column(db.String(300))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    business = db.Column(db.Text)
    advantage = db.Column(db.Text)
    highlight = db.Column(db.String(50))
    sort_order = db.Column(db.Integer, default=0)
