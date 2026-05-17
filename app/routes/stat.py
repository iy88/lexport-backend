from flask import Blueprint, jsonify
from app.services import stat_service

stat_bp = Blueprint('stat', __name__)


@stat_bp.route('', methods=['GET'])
def get_stats():
    result = stat_service.get_stats()
    return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
