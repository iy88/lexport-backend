import logging

import jwt as pyjwt
from flask import current_app
from flask_mail import Message
from sqlalchemy.exc import IntegrityError

from app.extensions import db, mail
from app.models.user import User
from app.utils.errors import ValidationError, AuthenticationError, ConflictError, NotFoundError
from app.utils.jwt_utils import generate_access_token, generate_verification_token, decode_token
from app.utils.validators import validate_username, validate_password, validate_email

logger = logging.getLogger(__name__)


def register(username, password, email):
    """Register a new user. Email is mandatory."""
    if not isinstance(username, str) or not isinstance(password, str) or not isinstance(email, str):
        raise ValidationError('用户名、密码和邮箱必须是字符串')

    username = username.strip()
    is_valid, err = validate_username(username)
    if not is_valid:
        raise ValidationError(err)

    is_valid, err = validate_password(password)
    if not is_valid:
        raise ValidationError(err)

    if not email.strip():
        raise ValidationError('邮箱为必填项')

    email = email.strip()
    is_valid, err = validate_email(email)
    if not is_valid:
        raise ValidationError(err)

    if User.query.filter_by(username=username).first():
        raise ConflictError('用户名已被注册')

    if User.query.filter_by(email=email).first():
        raise ConflictError('邮箱已被注册')

    user = User(username=username, email=email)
    user.set_password(password)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # Pre-checks improve the common response path, but the database
        # constraint is authoritative under concurrent registrations.
        if User.query.filter_by(username=username).first():
            raise ConflictError('用户名已被注册')
        if User.query.filter_by(email=email).first():
            raise ConflictError('邮箱已被注册')
        logger.exception('Registration violated an unexpected integrity constraint')
        raise ConflictError('用户名或邮箱已被注册')

    access_token = generate_access_token(user.id, user.role)
    verification_sent = _try_send_verification(user)

    return {
        'user': user.to_dict(),
        'access_token': access_token,
        'verification_email_sent': verification_sent,
    }


def _try_send_verification(user):
    """Send a verification email synchronously. Returns True on success."""
    if not user.email:
        return False
    try:
        token = generate_verification_token(user.id, user.email)
        verify_url = f"{current_app.config['FRONTEND_URL']}/verify-email/{token}"
        html = _render_verification_html(user.username, verify_url)
        plain = (
            f'您好 {user.username}，\n\n'
            f'请点击以下链接验证您的邮箱地址：\n{verify_url}\n\n'
            f'此链接将在30分钟内有效。\n\n律航出海'
        )
        msg = Message(
            subject='验证您的邮箱 - 律航出海',
            recipients=[user.email],
            body=plain,
            html=html,
        )
        mail.send(msg)
        return True
    except Exception:
        logger.exception('Failed to send verification email for user %s', user.id)
        return False


def login(login_id, password):
    if not isinstance(login_id, str) or not isinstance(password, str):
        raise ValidationError('登录账号和密码必须是字符串')

    login_id = login_id.strip()
    if not login_id or not password:
        raise ValidationError('请填写登录账号和密码')

    if '@' in login_id:
        user = User.query.filter_by(email=login_id).first()
    else:
        user = User.query.filter_by(username=login_id).first()

    if not user or not user.check_password(password):
        raise AuthenticationError('用户名或密码错误')

    access_token = generate_access_token(user.id, user.role)

    return {
        'user': user.to_dict(),
        'access_token': access_token,
    }


def verify_email(token):
    if not isinstance(token, str) or not token:
        raise ValidationError('缺少验证令牌')

    try:
        payload = decode_token(token, expected_type='verify_email')
    except pyjwt.ExpiredSignatureError:
        raise ValidationError('验证链接已过期')
    except pyjwt.InvalidTokenError:
        raise ValidationError('无效的验证令牌')

    raw_user_id = payload.get('sub')
    token_email = payload.get('email')

    if (
        not isinstance(raw_user_id, str)
        or not raw_user_id.isascii()
        or not raw_user_id.isdecimal()
        or raw_user_id.startswith('0')
        or len(raw_user_id) > 19
        or not isinstance(token_email, str)
        or not token_email
        or len(token_email) > 255
    ):
        raise ValidationError('无效的验证令牌')

    user_id = int(raw_user_id)
    if user_id <= 0 or user_id > 9_223_372_036_854_775_807:
        raise ValidationError('无效的验证令牌')

    # Serialize verification with change_email(). Without the row lock, an
    # old token can verify a newly written email between comparison and commit.
    user = (
        User.query.filter_by(id=user_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if not user:
        db.session.rollback()
        raise NotFoundError('用户不存在')

    if user.email != token_email:
        db.session.rollback()
        raise ValidationError('无效的验证令牌')

    user.email_verified = True
    db.session.commit()


def _render_verification_html(username, verify_url):
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f5f7fa;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:40px 16px;">
  <tr>
    <td align="center">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;">
        <!-- Header -->
        <tr>
          <td align="center" style="padding-bottom:24px;">
            <span style="font-size:20px;font-weight:700;background:linear-gradient(135deg,#1a4bb1,#0080ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">律航出海</span>
          </td>
        </tr>
        <!-- Card -->
        <tr>
          <td style="background-color:#ffffff;border-radius:12px;padding:40px 32px;box-shadow:0 4px 12px rgba(17,24,39,0.06);">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:18px;font-weight:600;color:#111827;padding-bottom:12px;">
                  验证您的邮箱地址
                </td>
              </tr>
              <tr>
                <td style="font-size:14px;line-height:24px;color:#6b7280;padding-bottom:24px;">
                  <p style="margin:0 0 8px 0;">您好，<strong style="color:#111827;">{username}</strong></p>
                  <p style="margin:0;">感谢您注册律航出海。请点击下方按钮完成邮箱验证，即可使用邮箱登录。</p>
                </td>
              </tr>
              <tr>
                <td align="center" style="padding-bottom:24px;">
                  <a href="{verify_url}" style="display:inline-block;background:linear-gradient(135deg,#1a4bb1,#0080ff);color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 36px;border-radius:8px;">验证邮箱</a>
                </td>
              </tr>
              <tr>
                <td style="font-size:13px;line-height:20px;color:#9ca3af;">
                  <p style="margin:0 0 4px 0;">此链接将在 <strong style="color:#6b7280;">30 分钟</strong> 内有效。</p>
                  <p style="margin:0;">如果按钮无法点击，请复制以下链接至浏览器：</p>
                </td>
              </tr>
              <tr>
                <td style="padding-top:8px;">
                  <span style="font-size:12px;line-height:18px;color:#9ca3af;word-break:break-all;">{verify_url}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td align="center" style="padding-top:24px;">
            <span style="font-size:12px;color:#9ca3af;">律航出海 · 非洲制造业法律数据整合平台</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>'''
