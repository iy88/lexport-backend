from flask import Blueprint, request, jsonify

from app.services import news_service
from app.utils.errors import AppError

news_bp = Blueprint('news', __name__)


@news_bp.route('', methods=['GET'])
def get_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    news_type = request.args.get('type')
    country_id = request.args.get('country_id')
    keyword = request.args.get('keyword')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    tag_id = request.args.get('tag_id', type=int)

    result = news_service.get_news(
        page=page,
        per_page=per_page,
        type=news_type,
        country_id=country_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        tag_id=tag_id,
    )
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200


@news_bp.route('/<int:news_id>', methods=['GET'])
def get_news_detail(news_id):
    try:
        result = news_service.get_news_detail(news_id)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()
