from app.extensions import db


def get_stats():
    rows = db.session.execute(db.text('SELECT id, value, label_zh, sort_order FROM platform_stats ORDER BY sort_order'))
    return {
        'stats': [{'id': r.id, 'value': r.value, 'label_zh': r.label_zh} for r in rows],
    }
