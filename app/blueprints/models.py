from flask import Blueprint, render_template, jsonify
import json
import os

models_bp = Blueprint('models', __name__)

@models_bp.route('/models')
def supported_models():
    """
    Render the Supported Models page
    """
    return render_template('supported_models.html')

@models_bp.route('/api/models')
def get_supported_models():
    """
    Get supported models data from config file
    """
    try:
        config_path = 'supported_models.json'
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({'models': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
