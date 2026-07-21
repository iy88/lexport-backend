import oss2
from flask import current_app

from app.utils.errors import AppError


def _get_bucket(bucket_name=None):
    """Get OSS bucket instance from current app config.

    Uses OSS_BUCKET_NAME by default; pass 'LAW_OSS_BUCKET_NAME' for the law
    knowledge-base bucket or directly pass a bucket name string.
    """
    if bucket_name == 'LAW_OSS_BUCKET_NAME':
        bucket_name = current_app.config.get('LAW_OSS_BUCKET_NAME', '')
        if not bucket_name:
            raise AppError('OSS_ERROR', '法律知识库 OSS Bucket 未配置', 502)
    elif not bucket_name:
        bucket_name = current_app.config['OSS_BUCKET_NAME']

    if not bucket_name:
        raise AppError('OSS_ERROR', 'OSS Bucket 未配置', 502)

    auth = oss2.AuthV4(
        current_app.config['OSS_ACCESS_KEY_ID'],
        current_app.config['OSS_ACCESS_KEY_SECRET'],
    )
    return oss2.Bucket(
        auth,
        current_app.config['OSS_ENDPOINT'],
        bucket_name,
        region=current_app.config['OSS_REGION'],
    )


def upload_file(local_path, object_name, bucket_name=None):
    """Upload a local file to OSS. Raises AppError('OSS_ERROR', 502) on failure."""
    try:
        bucket = _get_bucket(bucket_name)
        result = bucket.put_object_from_file(object_name, local_path)
        if result.status != 200:
            raise AppError('OSS_ERROR', f'OSS 上传返回异常状态码 {result.status}', 502)
    except AppError:
        raise
    except Exception as exc:
        raise AppError('OSS_ERROR', f'OSS 上传失败: {exc}', 502) from exc


def delete_object(object_name, bucket_name=None):
    """Delete an OSS object. Raises AppError('OSS_ERROR', 502) on failure.

    Deleting a non-existent object is a no-op (OSS returns 204 or 404 for
    a missing key; both are treated as success).
    """
    try:
        bucket = _get_bucket(bucket_name)
        result = bucket.delete_object(object_name)
        if result.status not in (200, 204):
            raise AppError('OSS_ERROR', f'OSS 删除返回异常状态码 {result.status}', 502)
    except AppError:
        raise
    except Exception as exc:
        if _is_not_found(exc):
            return  # already gone — safe to ignore
        raise AppError('OSS_ERROR', f'OSS 删除失败: {exc}', 502) from exc


def copy_object(source_name, dest_name, bucket_name=None):
    """Copy an OSS object within the same bucket.

    Raises AppError('OSS_ERROR', 502) on failure.
    """
    try:
        bucket = _get_bucket(bucket_name)
        result = bucket.copy_object(bucket.bucket_name, source_name, dest_name)
        if result.status != 200:
            raise AppError('OSS_ERROR', f'OSS 复制返回异常状态码 {result.status}', 502)
    except AppError:
        raise
    except Exception as exc:
        raise AppError('OSS_ERROR', f'OSS 复制失败: {exc}', 502) from exc


def head_object(object_name, bucket_name=None):
    """Get OSS object metadata.

    Returns a dict with keys: content_length, last_modified, etag.
    Raises AppError('OSS_ERROR', 502) on failure.
    """
    try:
        bucket = _get_bucket(bucket_name)
        result = bucket.head_object(object_name)
        if result.status != 200:
            raise AppError('OSS_ERROR', f'OSS HEAD 返回异常状态码 {result.status}', 502)
        return {
            'content_length': result.content_length,
            'last_modified': result.last_modified,
            'etag': result.etag,
        }
    except AppError:
        raise
    except Exception as exc:
        if _is_not_found(exc):
            raise AppError('OSS_NOT_FOUND', 'OSS 对象不存在', 404) from exc
        raise AppError('OSS_ERROR', f'OSS HEAD 失败: {exc}', 502) from exc


def download_file(object_name, local_path, bucket_name=None):
    """Download an OSS object to a local file.

    Raises AppError('OSS_ERROR', 502) on failure.
    """
    try:
        bucket = _get_bucket(bucket_name)
        result = bucket.get_object_to_file(object_name, local_path)
        if result.status != 200:
            raise AppError('OSS_ERROR', f'OSS 下载返回异常状态码 {result.status}', 502)
    except AppError:
        raise
    except Exception as exc:
        raise AppError('OSS_ERROR', f'OSS 下载失败: {exc}', 502) from exc


def object_exists(object_name, bucket_name=None):
    """Check whether an OSS object exists.

    Only a real OSS 404 is converted to ``False``.  Configuration,
    authentication, permission and transport failures remain errors so callers
    never mistake an unavailable bucket for an available object name.
    """
    try:
        bucket = _get_bucket(bucket_name)
        bucket.head_object(object_name)
        return True
    except AppError:
        raise
    except Exception as exc:
        if _is_not_found(exc):
            return False
        raise AppError('OSS_ERROR', f'OSS HEAD 失败: {exc}', 502) from exc


def _is_not_found(exc):
    """Return whether an oss2 exception represents a missing object."""
    no_such_key = getattr(oss2.exceptions, 'NoSuchKey', None)
    if no_such_key and isinstance(exc, no_such_key):
        return True
    return getattr(exc, 'status', None) == 404


def generate_signed_url(object_name, expires=None, bucket_name=None):
    """Generate a pre-signed GET URL for an OSS object.

    Raises AppError('OSS_ERROR', 502) on failure.
    """
    if expires is None:
        expires = current_app.config['OSS_SIGN_URL_EXPIRES']
    try:
        bucket = _get_bucket(bucket_name)
        return bucket.sign_url('GET', object_name, expires, slash_safe=True)
    except AppError:
        raise
    except Exception as exc:
        raise AppError('OSS_ERROR', f'生成签名 URL 失败: {exc}', 502) from exc
