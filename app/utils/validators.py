import re

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
    if not EMAIL_PATTERN.match(email):
        return False, '请输入正确的邮箱格式'
    return True, None
