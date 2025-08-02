from flask import Blueprint, request, jsonify

user_bp = Blueprint('user', __name__)

@user_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'API is running'})

@user_bp.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({'message': 'Test endpoint working'})
