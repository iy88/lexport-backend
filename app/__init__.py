import os

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

_DANGEROUS_SECRETS = frozenset({
    'dev-secret', 'dev-jwt-secret', 'change-me', 'your-secret-key',
    'your-secret-key-here-change-in-production',
    'your-jwt-secret-here-change-in-production',
})


def _env_value(name):
    """Return a stripped environment value for production validation."""
    return os.environ.get(name, '').strip()


def _validate_production_config(app):
    """Raise RuntimeError if production configuration is unsafe."""
    errors = []

    # Secrets
    for key in ('SECRET_KEY', 'JWT_SECRET_KEY'):
        raw_value = app.config.get(key, '')
        val = raw_value.strip() if isinstance(raw_value, str) else ''
        if len(val) < 32:
            errors.append(f'{key} 长度不能少于 32 个字符')
        if val.lower() in _DANGEROUS_SECRETS or val in _DANGEROUS_SECRETS:
            errors.append(f'{key} 不能使用示例/默认值')

    # Require explicit production values.  BaseConfig's development defaults
    # must never make an incomplete production environment look valid.
    for key in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'):
        if not _env_value(key):
            errors.append(f'{key} 未配置')

    # Redis
    if not _env_value('REDIS_URL'):
        errors.append('REDIS_URL 未配置')

    # SMTP
    for key in ('MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME', 'MAIL_PASSWORD',
                'MAIL_DEFAULT_SENDER'):
        if not _env_value(key):
            errors.append(f'{key} 未配置')

    # OSS
    oss_env_keys = {
        'OSS_ACCESS_KEY_ID': 'ALIBABA_CLOUD_ACCESS_KEY_ID',
        'OSS_ACCESS_KEY_SECRET': 'ALIBABA_CLOUD_ACCESS_KEY_SECRET',
        'OSS_REGION': 'OSS_REGION',
        'OSS_ENDPOINT': 'OSS_ENDPOINT',
        'OSS_BUCKET_NAME': 'OSS_BUCKET_NAME',
        'LAW_OSS_BUCKET_NAME': 'LAW_OSS_BUCKET_NAME',
    }
    for key, env_key in oss_env_keys.items():
        if not _env_value(env_key):
            errors.append(f'{key} 未配置')

    # Bailian
    for key in ('BAILIAN_API_KEY', 'REPORT_GENERATOR_APPID',
                'REPORT_AI_VERSION', 'REPORT_DATA_CUTOFF_DATE'):
        if not _env_value(key):
            errors.append(f'{key} 未配置')

    # Frontend
    frontend = _env_value('FRONTEND_URL')
    if not frontend:
        errors.append('FRONTEND_URL 未配置')
    elif not frontend.startswith('https://'):
        errors.append('FRONTEND_URL 必须使用 HTTPS')

    # CELERY_AUTO_START is a development feature
    if _env_value('CELERY_AUTO_START').lower() in ('1', 'true', 'yes'):
        errors.append('生产环境不允许 CELERY_AUTO_START=true')

    if errors:
        msg = '生产环境配置错误:\n' + '\n'.join(f'  - {e}' for e in errors)
        raise RuntimeError(msg)


def create_app(config_name=None):
    from config import DevelopmentConfig, ProductionConfig, TestingConfig

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig,
    }

    if config_name not in config_map:
        raise RuntimeError(
            f'未知的 FLASK_ENV 值: {config_name!r}。'
            f' 有效值: {", ".join(sorted(config_map))}'
        )

    config_class = config_map[config_name]

    app = Flask(__name__)
    app.config.from_object(config_class)

    if config_name == 'production':
        _validate_production_config(app)

    from app.extensions import db, mail, limiter

    db.init_app(app)
    mail.init_app(app)

    limiter.init_app(app)

    from app.routes import register_blueprints
    register_blueprints(app)

    from app.utils.errors import AppError

    @app.errorhandler(AppError)
    def handle_app_error(error):
        return error.to_response()

    from sqlalchemy.exc import DataError, StatementError

    def handle_invalid_database_value(error):
        db.session.rollback()
        return {
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': '字段类型或长度不合法',
            },
        }, 400

    app.register_error_handler(DataError, handle_invalid_database_value)
    app.register_error_handler(StatementError, handle_invalid_database_value)

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

    @app.errorhandler(413)
    def handle_request_too_large(e):
        return {
            'success': False,
            'error': {'code': 'FILE_TOO_LARGE', 'message': '上传文件总大小超过限制'}
        }, 413

    # Register rate-limit error handler (429)
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        return {
            'success': False,
            'error': {'code': 'RATE_LIMITED', 'message': '请求过于频繁，请稍后重试'},
        }, 429

    return app
