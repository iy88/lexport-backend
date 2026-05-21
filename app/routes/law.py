from flask import Blueprint, request, jsonify

from app.services import law_service

law_bp = Blueprint('law', __name__)


@law_bp.route('', methods=['GET'])
def get_laws():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
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
