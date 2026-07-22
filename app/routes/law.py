from flask import Blueprint, redirect, request, jsonify

from app.models.law import Law
from app.services import law_service
from app.utils.errors import AppError, NotFoundError
from app.utils.oss_utils import generate_signed_url, head_object

law_bp = Blueprint('law', __name__)


@law_bp.route('', methods=['GET'])
def get_laws():
    page = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int) or 20))
    country_id = request.args.get('country_id')
    scene_id = request.args.get('scene_id')
    keyword = request.args.get('keyword')

    result = law_service.get_laws(
        page=page,
        per_page=per_page,
        country_id=country_id,
        scene_id=scene_id,
        keyword=keyword,
    )
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@law_bp.route('/<int:law_id>', methods=['GET'])
def get_law_detail(law_id):
    try:
        result = law_service.get_law_detail(law_id)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@law_bp.route('/<int:law_id>/download', methods=['GET'])
def download_law_file(law_id):
    """Redirect to a pre-signed OSS URL for the published law file."""
    try:
        law = Law.query.filter_by(id=law_id, status='published').first()
        if not law:
            raise NotFoundError('法规不存在')
        if not law.object_name:
            raise NotFoundError('该法规无附件')

        # Do not redirect to a signed URL for a missing object.  OSS
        # configuration and transport errors remain 502 instead of being
        # disguised as a client-side 404.
        head_object(law.object_name, bucket_name='LAW_OSS_BUCKET_NAME')
        signed_url = generate_signed_url(
            law.object_name,
            bucket_name='LAW_OSS_BUCKET_NAME',
        )

        return redirect(signed_url, code=302)
    except AppError as e:
        return e.to_response()
