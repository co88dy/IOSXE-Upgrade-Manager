"""
Settings blueprint for credential management
"""

from flask import Blueprint, request, jsonify
import json
import os

settings_bp = Blueprint('settings', __name__)

# Path to config file
CONFIG_PATH = 'config.json'


@settings_bp.route('/api/settings/credentials', methods=['GET'])
def get_credentials():
    """
    Get current credentials (without passwords for security)
    """
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        return jsonify({
            'username': config['credentials']['ssh_username'],
            'netconf_port': config['credentials']['netconf_port'],
            'has_enable_password': bool(config['credentials'].get('enable_password'))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/credentials', methods=['POST'])
def update_credentials():
    """
    Update credentials in config.json
    Request body: {"username": "admin", "password": "cisco", "enable_password": "secret", "netconf_port": 830}
    """
    try:
        data = request.get_json()
        
        username = data.get('username')
        password = data.get('password')
        enable_password = data.get('enable_password', '')
        netconf_port = data.get('netconf_port', 830)
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Read current config
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # Update credentials
        config['credentials']['ssh_username'] = username
        config['credentials']['ssh_password'] = password
        config['credentials']['enable_password'] = enable_password
        config['credentials']['netconf_port'] = netconf_port
        
        # Write back to file
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'message': 'Credentials updated successfully',
            'username': username,
            'netconf_port': netconf_port,
            'has_enable_password': bool(enable_password)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/get', methods=['GET'])
def get_settings():
    """
    Get all settings including HTTP server IP
    """
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        return jsonify({
            'http_server_ip': config.get('http_server_ip', '')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/save', methods=['POST'])
def save_settings():
    """
    Save general settings (e.g., HTTP server IP)
    """
    try:
        data = request.get_json()
        
        # Read current config
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # Update http_server_ip if provided
        if 'http_server_ip' in data:
            config['http_server_ip'] = data['http_server_ip']
        
        # Write back to file
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'message': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
