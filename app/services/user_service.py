import logging

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from app.services.auth_service import _try_send_verification
from app.utils.errors import AppError, ConflictError, ValidationError
from app.utils.validators import validate_email

logger = logging.getLogger(__name__)


def get_profile(user):
    return {'user': user.to_dict()}


def change_email(user, new_email, password):
    """Change or bind an email. Requires current password."""
    if not isinstance(new_email, str) or not isinstance(password, str):
        raise ValidationError('邮箱和密码必须是字符串')

    if not password:
        raise ValidationError('请输入当前密码')

    new_email = new_email.strip()
    if not new_email:
        raise ValidationError('邮箱不能为空')

    is_valid, err = validate_email(new_email)
    if not is_valid:
        raise ValidationError(err)

    # Use the same row lock as email verification so an old verification
    # token can never mark a replacement email as verified.
    locked_user = (
        User.query.filter_by(id=user.id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if not locked_user:
        db.session.rollback()
        raise AppError('AUTH_ERROR', '用户不存在', 401)

    if not locked_user.check_password(password):
        db.session.rollback()
        raise AppError('AUTH_ERROR', '密码错误', 403)

    # Check uniqueness
    existing = User.query.filter(User.email == new_email, User.id != locked_user.id).first()
    if existing:
        db.session.rollback()
        raise ConflictError('该邮箱已被其他账号使用')

    # If same as current verified email, reject
    if new_email == locked_user.email and locked_user.email_verified:
        db.session.rollback()
        raise ConflictError('该邮箱已验证，无需重复绑定')

    locked_user.email = new_email
    locked_user.email_verified = False
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ConflictError('该邮箱已被其他账号使用')

    verification_sent = _try_send_verification(locked_user)

    return {
        'user': locked_user.to_dict(),
        'verification_email_sent': verification_sent,
    }


def resend_verification(user):
    """Resend verification email."""
    fresh_user = User.query.filter_by(id=user.id).populate_existing().one_or_none()
    if not fresh_user:
        raise AppError('AUTH_ERROR', '用户不存在', 401)

    if not fresh_user.email:
        raise ValidationError('未绑定邮箱')

    if fresh_user.email_verified:
        raise ConflictError('邮箱已验证')

    ok = _try_send_verification(fresh_user)
    if not ok:
        raise AppError('EMAIL_SEND_FAILED', '邮件发送失败，请稍后重试', 502)

    return {'user': fresh_user.to_dict()}
