from flask import Blueprint, request, jsonify

from app.services import news_service
from app.utils.errors import AppError

news_bp = Blueprint('news', __name__)


@news_bp.route('', methods=['GET'])
def get_news():
    page = max(1, request.args.get('page', 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int) or 20))
    news_type = request.args.get('type')
    country_id = request.args.get('country_id')
    keyword = request.args.get('keyword')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    raw_tag_id = request.args.get('tag_id')
    if raw_tag_id is not None:
        try:
            tag_id = int(raw_tag_id)
        except (TypeError, ValueError) as exc:
            raise AppError('VALIDATION_ERROR', 'tag_id 必须为整数', 400) from exc
        if tag_id <= 0:
            raise AppError('VALIDATION_ERROR', 'tag_id 必须为正整数', 400)
    else:
        tag_id = None

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
