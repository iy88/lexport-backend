import os

from flask import Blueprint, current_app, request, jsonify, send_file

from app.models.law import Law
from app.services import law_service
from app.utils.errors import AppError, NotFoundError

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


@law_bp.route('/<int:law_id>', methods=['GET'])
def get_law_detail(law_id):
    try:
        result = law_service.get_law_detail(law_id)
        return jsonify({'success': True, 'data': result, 'message': '成功'}), 200
    except AppError as e:
        return e.to_response()


@law_bp.route('/<int:law_id>/download', methods=['GET'])
def download_law_file(law_id):
    try:
        law = Law.query.filter_by(id=law_id, status='published').first()
        if not law:
            raise NotFoundError('法规不存在')
        if not law.secure_name:
            raise NotFoundError('该法规无附件')
        upload_dir = os.path.join(current_app.config['UPLOAD_PATH'], 'laws')
        file_path = os.path.join(upload_dir, law.secure_name)
        if not os.path.isfile(file_path):
            raise NotFoundError('文件丢失，请联系管理员')
        return send_file(
            file_path,
            download_name=law.filename, as_attachment=True
        )
    except AppError as e:
        return e.to_response()
