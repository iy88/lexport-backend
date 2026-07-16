from flask import Blueprint, request, jsonify

from app.services import agency_service

agency_bp = Blueprint('agency', __name__)


@agency_bp.route('', methods=['GET'])
def get_agencies():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    scene_id = request.args.get('scene_id')
    category_id = request.args.get('category_id')
    keyword = request.args.get('keyword')
    region = request.args.get('region')

    result = agency_service.get_agencies(
        page=page,
        per_page=per_page,
        scene_id=scene_id,
        category_id=category_id,
        keyword=keyword,
        region=region,
    )
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
