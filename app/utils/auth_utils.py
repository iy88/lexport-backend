from functools import wraps

import jwt as pyjwt
from flask import request, g

from app.extensions import db
from app.models.user import User
from app.utils.errors import AuthenticationError
from app.utils.jwt_utils import decode_token


def jwt_required(func=None, *, role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            header = request.headers.get('Authorization', '')
            if not header.startswith('Bearer '):
                raise AuthenticationError('缺少认证令牌')

            token = header[7:]

            try:
                payload = decode_token(token, expected_type='access')
            except pyjwt.ExpiredSignatureError:
                raise AuthenticationError('认证令牌已过期')
            except pyjwt.InvalidTokenError:
                raise AuthenticationError('无效的认证令牌')

            user_id = payload.get('sub')
            user = db.session.get(User, int(user_id))
            if not user:
                raise AuthenticationError('用户不存在')

            if role is not None and user.role != role:
                raise AuthenticationError('权限不足', http_status=403)

            g.current_user = user
            return f(*args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
