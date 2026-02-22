"""
Settings blueprint for credential management
"""

from flask import Blueprint, request, jsonify
import json
import os
import socket

settings_bp = Blueprint('settings', __name__)

# Path to config file
CONFIG_PATH = 'config.json'


def _get_all_server_ips() -> list:
    """
    Return all non-loopback IPv4 addresses on this host, in a form suitable
    for the dropdown.  Tries platform-native commands first so every interface
    (VPN, Tailscale, docker0, etc.) is included, then falls back to socket.
    """
    import subprocess
    import re
    import platform

    ips = []
    seen = set()

    def add(ip, label=None):
        if ip and ip not in ('127.0.0.1', '0.0.0.0') and ip not in seen:
            ips.append({'ip': ip, 'label': label or ip})
            seen.add(ip)

    # --- 1. Parse all interfaces from OS commands ---
    try:
        system = platform.system()
        if system == 'Darwin':
            # macOS
            out = subprocess.check_output(['ifconfig'], text=True, timeout=5)
            # Match lines like: "    inet 192.168.1.5 netmask ..."
            for m in re.finditer(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out):
                add(m.group(1))
        else:
            # Linux / Docker
            out = subprocess.check_output(
                ['ip', '-4', 'addr', 'show'], text=True, timeout=5
            )
            for m in re.finditer(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out):
                add(m.group(1))
    except Exception:
        pass

    # --- 2. UDP connect trick (primary outbound interface) as supplement ---
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        primary = s.getsockname()[0]
        s.close()
        add(primary)
    except Exception:
        pass

    # --- 3. Label the first entry as (primary) if there are multiple ---
    if ips:
        ips[0]['label'] = f"{ips[0]['ip']} (primary)"

    return ips


@settings_bp.route('/api/settings/server-ips', methods=['GET'])
def get_server_ips():
    """Return all detected server IPs and the currently saved http_server_ip."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        saved_ip = config.get('http_server_ip', '')
    except Exception:
        saved_ip = ''

    detected = _get_all_server_ips()

    # If saved IP isn't in detected list, add it so it shows in the dropdown
    if saved_ip and not any(d['ip'] == saved_ip for d in detected):
        detected.append({'ip': saved_ip, 'label': f'{saved_ip} (saved)'})

    return jsonify({'ips': detected, 'saved_ip': saved_ip})


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
