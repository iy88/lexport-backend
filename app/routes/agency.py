from flask import Blueprint, request, jsonify

from app.services import agency_service

agency_bp = Blueprint('agency', __name__)


@agency_bp.route('', methods=['GET'])
def get_agencies():
    page = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int) or 20))
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
