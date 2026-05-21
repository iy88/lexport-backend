from dotenv import load_dotenv
from flask import Flask

load_dotenv()


def create_app(config_name=None):
    from config import DevelopmentConfig, ProductionConfig, TestingConfig

    if config_name is None:
        config_name = 'development'

    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig,
    }
    config_class = config_map.get(config_name, DevelopmentConfig)

    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.extensions import db, mail
    db.init_app(app)
    mail.init_app(app)

    from app.routes import register_blueprints
    register_blueprints(app)

    from app.utils.errors import AppError
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return error.to_response()

    @app.errorhandler(404)
    def handle_404(e):
        from app.utils.errors import NotFoundError
        return NotFoundError('资源不存在').to_response()

    @app.errorhandler(500)
    def handle_500(e):
        return {
            'success': False,
            'error': {'code': 'INTERNAL_ERROR', 'message': '服务器内部错误'}
        }, 500

    with app.app_context():
        db.create_all()
        db.session.execute(db.text(
            "CREATE OR REPLACE VIEW platform_stats AS "
            "SELECT 'countries' AS id, CAST(COUNT(*) AS CHAR) AS value, '覆盖国家（持续拓展中）' AS label_zh, 1 AS sort_order FROM countries "
            "UNION ALL SELECT 'laws', CAST(COUNT(*) AS CHAR), '法规条文收录', 2 FROM laws "
            "UNION ALL SELECT 'scenes', CAST(COUNT(*) AS CHAR), '高频合规场景', 3 FROM compliance_scenes "
            "UNION ALL SELECT 'agencies', CAST(COUNT(*) AS CHAR), '合作合规机构', 4 FROM agencies"
        ))
        db.session.commit()

    return app
