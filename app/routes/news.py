from flask import Blueprint, request, jsonify

from app.services import news_service

news_bp = Blueprint('news', __name__)


@news_bp.route('', methods=['GET'])
def get_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    news_type = request.args.get('type')
    country_id = request.args.get('country_id')
    keyword = request.args.get('keyword')

    result = news_service.get_news(
        page=page,
        per_page=per_page,
        type=news_type,
        country_id=country_id,
        keyword=keyword,
    )
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
