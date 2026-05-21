from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app


def generate_access_token(user_id, role):
    delta = timedelta(seconds=current_app.config['JWT_ACCESS_TOKEN_EXPIRES'])
    payload = {
        'sub': str(user_id),
        'role': role,
        'type': 'access',
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + delta,
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')


def generate_verification_token(user_id, email):
    delta = timedelta(seconds=current_app.config['JWT_VERIFY_TOKEN_EXPIRES'])
    payload = {
        'sub': str(user_id),
        'email': email,
        'type': 'verify_email',
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + delta,
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')


def decode_token(token, expected_type=None):
    payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    if expected_type and payload.get('type') != expected_type:
        raise jwt.InvalidTokenError('Invalid token type')
    return payload
