import os


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    JWT_VERIFY_TOKEN_EXPIRES = int(os.environ.get('JWT_VERIFY_TOKEN_EXPIRES', 1800))

    _DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    _DB_PORT = os.environ.get('DB_PORT', '3306')
    _DB_NAME = os.environ.get('DB_NAME', 'lexport')
    _DB_USER = os.environ.get('DB_USER', 'root')
    _DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{_DB_USER}:{_DB_PASSWORD}@'
        f'{_DB_HOST}:{_DB_PORT}/{_DB_NAME}'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.example.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    _MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USE_SSL = _MAIL_USE_SSL
    MAIL_USE_TLS = _MAIL_USE_SSL is False and os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'LexPort <noreply@lexport.cn>')

    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://lexport.cn')

    UPLOAD_PATH = os.environ.get('UPLOAD_PATH', './uploads')


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
