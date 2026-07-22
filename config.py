import os

from sqlalchemy.engine.url import URL


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    JWT_VERIFY_TOKEN_EXPIRES = int(os.environ.get('JWT_VERIFY_TOKEN_EXPIRES', 1800))

    _DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    _DB_PORT = int(os.environ.get('DB_PORT', '3306'))
    _DB_NAME = os.environ.get('DB_NAME', 'lexport')
    _DB_USER = os.environ.get('DB_USER', 'root')
    _DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

    SQLALCHEMY_DATABASE_URI = URL.create(
        'mysql+pymysql',
        username=_DB_USER,
        password=_DB_PASSWORD,
        host=_DB_HOST,
        port=_DB_PORT,
        database=_DB_NAME,
        query={'charset': 'utf8mb4'},
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_timeout': 10,
    }

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.example.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    _MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USE_SSL = _MAIL_USE_SSL
    MAIL_USE_TLS = _MAIL_USE_SSL is False and os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'LexPort <noreply@lexport.cn>')

    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://lexport.cn')

    UPLOAD_PATH = os.path.abspath(os.environ.get('UPLOAD_PATH', './uploads'))
    # Five 20MB documents plus multipart form overhead.
    MAX_CONTENT_LENGTH = 105 * 1024 * 1024

    # OSS (Alibaba Cloud Object Storage)
    OSS_ACCESS_KEY_ID = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID', '')
    OSS_ACCESS_KEY_SECRET = os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET', '')
    OSS_REGION = os.environ.get('OSS_REGION', 'cn-beijing')
    OSS_ENDPOINT = os.environ.get('OSS_ENDPOINT', 'https://oss-cn-beijing.aliyuncs.com')
    OSS_BUCKET_NAME = os.environ.get('OSS_BUCKET_NAME', '')
    LAW_OSS_BUCKET_NAME = os.environ.get('LAW_OSS_BUCKET_NAME', '')
    OSS_SIGN_URL_EXPIRES = int(os.environ.get('OSS_SIGN_URL_EXPIRES', 7200))

    # Bailian (百炼) AI Platform
    BAILIAN_API_KEY = os.environ.get('BAILIAN_API_KEY', '')
    BAILIAN_BASE_URL = os.environ.get('BAILIAN_BASE_URL', 'https://dashscope.aliyuncs.com')
    REPORT_GENERATOR_APPID = os.environ.get('REPORT_GENERATOR_APPID', '')
    REPORT_AI_VERSION = os.environ.get('REPORT_AI_VERSION', '')
    REPORT_DATA_CUTOFF_DATE = os.environ.get('REPORT_DATA_CUTOFF_DATE', '')

    # Redis / Celery
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    RATELIMIT_STORAGE_URI = REDIS_URL
    REPORT_POLL_INTERVAL_SECONDS = int(os.environ.get('REPORT_POLL_INTERVAL_SECONDS', 10))
    REPORT_TASK_TIMEOUT_SECONDS = int(os.environ.get('REPORT_TASK_TIMEOUT_SECONDS', 7200))


class CeleryConfig:
    broker_url = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    result_backend = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'Asia/Shanghai'
    enable_utc = True
    broker_connection_retry_on_startup = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # MySQL pool options are incompatible with SQLite
    RATELIMIT_STORAGE_URI = 'memory://'
