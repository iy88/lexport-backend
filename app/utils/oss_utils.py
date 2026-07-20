import oss2
from flask import current_app


def _get_bucket():
    """Get OSS bucket instance from current app config."""
    auth = oss2.AuthV4(
        current_app.config['OSS_ACCESS_KEY_ID'],
        current_app.config['OSS_ACCESS_KEY_SECRET'],
    )
    return oss2.Bucket(
        auth,
        current_app.config['OSS_ENDPOINT'],
        current_app.config['OSS_BUCKET_NAME'],
        region=current_app.config['OSS_REGION'],
    )


def upload_file(local_path, object_name):
    """Upload a local file to OSS. Returns True on success, False on failure."""
    try:
        bucket = _get_bucket()
        result = bucket.put_object_from_file(object_name, local_path)
        return result.status == 200
    except Exception:
        return False


def generate_signed_url(object_name, expires=None):
    """Generate a pre-signed GET URL for an OSS object."""
    if expires is None:
        expires = current_app.config['OSS_SIGN_URL_EXPIRES']
    bucket = _get_bucket()
    return bucket.sign_url('GET', object_name, expires, slash_safe=True)
