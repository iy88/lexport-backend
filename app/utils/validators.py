import re

from sqlalchemy.sql.sqltypes import String

from app.utils.errors import ValidationError

USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,50}$')
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def validate_username(username):
    if not username or not USERNAME_PATTERN.match(username):
        return False, '用户名需为3-50位字母、数字或下划线'
    return True, None


def validate_password(password):
    if not password or len(password) < 8:
        return False, '密码长度不少于8位'
    if not re.search(r'[a-zA-Z]', password):
        return False, '密码需包含字母'
    if not re.search(r'\d', password):
        return False, '密码需包含数字'
    return True, None


def validate_email(email):
    if not email:
        return True, None
    if not isinstance(email, str) or len(email) > 255:
        return False, '请输入正确的邮箱格式'
    if not EMAIL_PATTERN.match(email):
        return False, '请输入正确的邮箱格式'
    return True, None


def normalize_model_strings(model, values, required=()):
    """Trim and validate string values against SQLAlchemy column lengths."""
    normalized = dict(values)
    required = set(required)
    for field, value in values.items():
        column = model.__table__.columns.get(field)
        if column is None or not isinstance(column.type, String):
            continue
        if value is None:
            if field in required:
                raise ValidationError(f'{field} 不能为空')
            continue
        if not isinstance(value, str):
            raise ValidationError(f'{field} 必须为字符串')
        value = value.strip()
        if field in required and not value:
            raise ValidationError(f'{field} 不能为空')
        max_length = getattr(column.type, 'length', None)
        if max_length is not None and len(value) > max_length:
            raise ValidationError(f'{field} 长度不能超过 {max_length} 个字符')
        normalized[field] = value
    return normalized
