from flask import Flask
from dotenv import load_dotenv

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

    return app
