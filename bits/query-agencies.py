from app import create_app
from app.extensions import db
from app.models.agency import Agency

app = create_app()

with app.app_context():
    agencies = Agency.query.filter(Agency.region.contains('尼日利亚')).all()
    lines = [
        f'机构名称：{a.name}，适配业务：{a.business or "无"}，核心优势：{a.advantage or "无"}'
        for a in agencies
    ]
    print('\n'.join(lines))
