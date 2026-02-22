"""
Discovery blueprint for device discovery and NETCONF management
"""

from flask import Blueprint, request, jsonify
from app.database.models import Database, InventoryModel, JobsModel, PreChecksModel
from app.utils.netconf_client import NetconfClient
from app.utils.ssh_client import SSHClient
import json
import os
import glob
import re

discovery_bp = Blueprint('discovery', __name__)

# Load config helper
def get_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

# Initialize DB with initial config
initial_config = get_config()
db = Database(initial_config.get('database', {}).get('path', 'app/database/network_inventory.db'))

# Load supported models patterns
SUPPORTED_MODELS_CACHE = []

def load_supported_models():
    """Load supported models patterns from config file"""
    global SUPPORTED_MODELS_CACHE
    try:
        with open('supported_models.json', 'r') as f:
            data = json.load(f)
            patterns = []
            for family in data.get('models', []):
                for series in family.get('series', []):
                    # Store as object with patterns and image_format
                    patterns.append({
                        'patterns': series.get('patterns', []),
                        'image_format': series.get('image_format', '')
                    })
            SUPPORTED_MODELS_CACHE = patterns
    except Exception as e:
        print(f"Error loading supported models: {e}")
        SUPPORTED_MODELS_CACHE = []

def is_model_supported(model_name):
    """Check if model is supported based on regex patterns"""
    if not SUPPORTED_MODELS_CACHE:
        load_supported_models()
    
    # If model is Unknown, it's not supported
    if not model_name or model_name == 'Unknown':
        return 'No'
        
    for entry in SUPPORTED_MODELS_CACHE:
        for pattern in entry.get('patterns', []):
            if re.match(pattern, model_name, re.IGNORECASE):
                return 'Yes'
            
    return 'No'

def get_image_regex_for_model(model_name):
    """Get regex for compatible images based on model"""
    if not SUPPORTED_MODELS_CACHE:
        load_supported_models()

    if not model_name or model_name == 'Unknown':
        return None

    for entry in SUPPORTED_MODELS_CACHE:
        for pattern in entry.get('patterns', []):
            if re.match(pattern, model_name, re.IGNORECASE):
                image_format = entry.get('image_format', '')
                if image_format:
                    # Convert format string to regex
                    # e.g., cat9k_iosxe.<release>.SPA.bin -> ^cat9k_iosxe\..*\.SPA\.bin$
                    # Escape dots
                    regex = re.escape(image_format)
                    # Replace <release> with .*
                    regex = regex.replace(re.escape('<release>'), '.*')
                    return f"^{regex}$"
    return None

@discovery_bp.route('/api/discover', methods=['POST'])
def discover_devices():
    """
    Discover devices from provided IP list
    Request body: {"ip_list": ["10.10.20.1", "10.10.20.2"]}
    """
    data = request.get_json()
    ip_list = data.get('ip_list', [])
    
    if not ip_list:
        return jsonify({'error': 'No IP addresses provided'}), 400
    
    # Reload config to get latest credentials
    config = get_config()
    
    results = []
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    netconf_port = config['credentials']['netconf_port']
    
    for ip in ip_list:
        try:
            # Try NETCONF first
            netconf = NetconfClient(ip, netconf_port, username, password)
            netconf_success = False
            
            if netconf.connect():
                # Get hardware info
                hardware_info = netconf.get_device_hardware()
                system_info = netconf.get_system_info()
                filesystem_info = netconf.get_filesystem_info()
                boot_info = netconf.get_boot_variables()
                
                if hardware_info and system_info:
                    # Determine device role
                    device_role = netconf.determine_device_role(hardware_info['part_number'])
                    
                    # Check for existing device
                    existing_dev = InventoryModel.get_device(db, ip)
                    
                    free_space_mb = int(filesystem_info.get('available_gb', 0) * 1024) if filesystem_info else None
                    boot_variable = boot_info.get('boot_system') if boot_info else None
                    config_register = boot_info.get('config_register') if boot_info else 'Unknown'
                    if config_register == 'Unknown':
                        config_register = None

                    # Compute initial version from NETCONF hardware info
                    # (hardware 'version' field is often a HW revision like 'V00', not the SW version)
                    actual_version = hardware_info.get('sw_version')
                    if not actual_version or actual_version == 'Unknown':
                        actual_version = system_info.get('version', 'Unknown')
                    
                    # If C8000V/CSR1000V virtualization models return empty, selectively fallback to SSH
                    # Also fall back for sw_version when it looks like a hardware revision (e.g. 'V00')
                    # or a full Cisco IOS banner string (e.g. 'Cisco IOS Software [Bengaluru]...')
                    import re as _re
                    hw_version_looks_invalid = (
                        not actual_version
                        or actual_version == 'Unknown'
                        or bool(_re.match(r'^V\d+$', str(actual_version).strip()))
                        or not bool(_re.match(r'^\d+\.\d+', str(actual_version).strip()))  # not a clean X.X version
                    )
                    ssh_version_info = None
                    if free_space_mb is None or boot_variable is None or config_register is None or hw_version_looks_invalid:
                        print(f"[INFO] NETCONF succeeded for {ip} but missing partial data (version={actual_version}). Falling back to SSH for missing fields.")
                        ssh_fallback = SSHClient(ip, username, password, enable_password)
                        if ssh_fallback.connect():
                            if free_space_mb is None:
                                free_space_mb = ssh_fallback.get_free_space_mb()
                            if boot_variable is None:
                                boot_variable = ssh_fallback.get_boot_variables()
                            # Fetch version info once if needed for config_register or version
                            if config_register is None or hw_version_looks_invalid:
                                ssh_version_info = ssh_fallback.get_version_info()
                            if config_register is None and ssh_version_info:
                                config_register = ssh_version_info.get('config_register', 'Unknown')
                            if hw_version_looks_invalid and ssh_version_info:
                                actual_version = ssh_version_info.get('version', actual_version)
                            ssh_fallback.disconnect()

                    # Derive ROMMON from SSH version info if available, otherwise N/A
                    rommon_version = (ssh_version_info.get('rommon_version', 'N/A') if ssh_version_info else 'N/A')

                    device_data = {
                        'ip_address': ip,
                        'hostname': system_info.get('hostname', 'Unknown'),
                        'serial_number': hardware_info.get('serial_number', 'Unknown'),
                        'device_role': device_role,
                        'current_version': actual_version,
                        'rommon_version': rommon_version,
                        'config_register': config_register,
                        'status': 'Online',
                        'netconf_state': 'Enabled',
                        'model': hardware_info.get('part_number', 'Unknown'),
                        'boot_variable': boot_variable,
                        'free_space_mb': free_space_mb,
                        'image_file': str(boot_variable).split(',')[0] if boot_variable else None,
                        'precheck_status': existing_dev.get('precheck_status') if existing_dev else None,
                        'precheck_details': existing_dev.get('precheck_details') if existing_dev else None,
                        'target_image': existing_dev.get('target_image') if existing_dev else None,
                        'image_copied': existing_dev.get('image_copied', 'No') if existing_dev else 'No',
                        'image_verified': existing_dev.get('image_verified', 'No') if existing_dev else 'No',
                        'is_supported': is_model_supported(hardware_info.get('part_number', 'Unknown'))
                    }
                    
                    # Add to database
                    print(f"DEBUG: Adding device {ip} with data: {device_data}")
                    try:
                        if InventoryModel.add_device(db, device_data):
                            results.append({'ip': ip, 'status': 'success', 'method': 'NETCONF'})
                            netconf_success = True
                        else:
                            print(f"ERROR: Failed to add device {ip} to database")
                            results.append({'ip': ip, 'status': 'failed', 'error': 'Database insertion failed (Check server logs)'})
                            netconf_success = False
                    except Exception as e:
                        print(f"ERROR: Exception adding device {ip}: {e}")
                        results.append({'ip': ip, 'status': 'failed', 'error': f'Database error: {str(e)}'})
                        netconf_success = False
                else:
                    print(f"[WARN] NETCONF connected to {ip} but could not retrieve device info (likely insufficient privileges). Falling back to SSH.")
                
                netconf.disconnect()
            
            # Fallback to SSH if NETCONF failed to connect or retrieve data
            if not netconf_success:
                ssh = SSHClient(ip, username, password, enable_password)
                if ssh.connect():
                    version_info = ssh.get_version_info()
                    
                    # Check actual NETCONF status on the device
                    netconf_state = ssh.check_netconf_status()
                    
                    # Collect boot variables and free space
                    boot_var = ssh.get_boot_variables()
                    free_space = ssh.get_free_space_mb()
                    
                    if version_info:
                        # Check for existing device to preserve user settings
                        existing_dev = InventoryModel.get_device(db, ip)
                        
                        device_data = {
                            'ip_address': ip,
                            'hostname': version_info.get('hostname', 'Unknown'),
                            'serial_number': version_info.get('serial_number', 'Unknown'),
                            'device_role': netconf.determine_device_role(version_info.get('model', 'Unknown')),
                            'current_version': version_info.get('version', 'Unknown'),
                            'rommon_version': 'N/A',
                            'config_register': version_info.get('config_register', 'Unknown'),
                            'status': 'Online',
                            'netconf_state': netconf_state,  # Use actual status from device
                            'model': version_info.get('model', 'Unknown'),
                            'boot_variable': boot_var,
                            'free_space_mb': free_space,
                            'image_file': version_info.get('image_file'),
                            'rommon_version': version_info.get('rommon_version', 'N/A'),
                            'precheck_status': existing_dev.get('precheck_status') if existing_dev else None,
                            'precheck_details': existing_dev.get('precheck_details') if existing_dev else None,
                            'target_image': existing_dev.get('target_image') if existing_dev else None,
                            'image_copied': existing_dev.get('image_copied', 'No') if existing_dev else 'No',
                            'image_verified': existing_dev.get('image_verified', 'No') if existing_dev else 'No',
                            'is_supported': is_model_supported(version_info.get('model', 'Unknown'))
                        }
                        
                        print(f"DEBUG: Adding device {ip} (SSH) with data: {device_data}")
                        try:
                            if InventoryModel.add_device(db, device_data):
                                results.append({'ip': ip, 'status': 'success', 'method': 'SSH'})
                            else:
                                print(f"ERROR: Failed to add device {ip} (SSH) to database")
                                results.append({'ip': ip, 'status': 'failed', 'error': 'Database insertion failed (Check server logs)'})
                        except Exception as e:
                            print(f"ERROR: Exception adding device {ip} (SSH): {e}")
                            results.append({'ip': ip, 'status': 'failed', 'error': f'Database error: {str(e)}'})
                    else:
                        results.append({'ip': ip, 'status': 'failed', 'error': 'Could not retrieve version info'})
                    
                    ssh.disconnect()
                else:
                    results.append({'ip': ip, 'status': 'failed', 'error': 'Connection failed'})
        except Exception as e:
            results.append({'ip': ip, 'status': 'failed', 'error': str(e)})
    
    return jsonify({'results': results})


@discovery_bp.route('/api/netconf/sync-state', methods=['POST'])
def sync_netconf_state():
    """
    Update the DB netconf_state for a device without touching the device.
    Body: {"ip": "10.10.20.1", "netconf_state": "Enabled"}
    Used to reconcile DB with the live state discovered via SSH check.
    """
    data = request.get_json()
    ip = data.get('ip', '').strip()
    state = data.get('netconf_state', '').strip()

    if not ip or state not in ('Enabled', 'Disabled'):
        return jsonify({'error': 'ip and valid netconf_state required'}), 400

    db = Database()
    success = InventoryModel.update_netconf_state(db, ip, state)
    if success:
        print(f"[INFO] /api/netconf/sync-state: updated {ip} → {state} in DB")
        return jsonify({'ip': ip, 'netconf_state': state, 'updated': True})
    else:
        return jsonify({'error': 'DB update failed'}), 500


@discovery_bp.route('/api/netconf/status', methods=['GET'])
def get_netconf_status():
    """
    Check the live NETCONF state on a device via SSH.
    Query param: ?ip=10.10.20.1
    Returns: {"ip": "...", "netconf_state": "Enabled"|"Disabled"|"Unknown"}
    """
    ip = request.args.get('ip', '').strip()
    if not ip:
        return jsonify({'error': 'ip query parameter required'}), 400

    config = get_config()
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')

    try:
        ssh = SSHClient(ip, username, password, enable_password)
        if ssh.connect():
            print(f"[INFO] /api/netconf/status: SSH connected to {ip}, checking state...")
            state = ssh.check_netconf_status()
            ssh.disconnect()
            print(f"[INFO] /api/netconf/status: {ip} → {state}")
            return jsonify({'ip': ip, 'netconf_state': state})
        else:
            print(f"[WARN] /api/netconf/status: SSH connection failed to {ip}")
            return jsonify({'ip': ip, 'netconf_state': 'Unknown', 'error': 'SSH connection failed'})
    except Exception as e:
        print(f"[ERROR] /api/netconf/status: {ip} → {e}")
        return jsonify({'ip': ip, 'netconf_state': 'Unknown', 'error': str(e)}), 500


@discovery_bp.route('/api/netconf/toggle', methods=['POST'])
def toggle_netconf():
    """
    Enable or disable NETCONF on selected devices
    Request body: {"ip_list": ["10.10.20.1"], "action": "enable"}
    """
    data = request.get_json()
    ip_list = data.get('ip_list', [])
    action = data.get('action', 'enable')
    
    if not ip_list:
        return jsonify({'error': 'No IP addresses provided'}), 400
    
    # Reload config
    config = get_config()
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    
    results = []
    
    for ip in ip_list:
        try:
            ssh = SSHClient(ip, username, password, enable_password)
            if ssh.connect():
                if action == 'toggle':
                    current_state = ssh.check_netconf_status()
                    if current_state == 'Enabled':
                        success = ssh.disable_netconf()
                        new_state = 'Disabled' if success else 'Enabled'
                    else:
                        success = ssh.enable_netconf()
                        new_state = 'Enabled' if success else 'Disabled'
                elif action == 'enable':
                    success = ssh.enable_netconf()
                    new_state = 'Enabled' if success else 'Disabled'
                else:
                    success = ssh.disable_netconf()
                    new_state = 'Disabled' if success else 'Enabled'
                
                # Update database
                InventoryModel.update_netconf_state(db, ip, new_state)
                
                results.append({
                    'ip': ip,
                    'status': 'success' if success else 'failed',
                    'netconf_state': new_state
                })
                
                ssh.disconnect()
            else:
                results.append({'ip': ip, 'status': 'failed', 'error': 'Connection failed'})
        except Exception as e:
            results.append({'ip': ip, 'status': 'failed', 'error': str(e)})
    
    return jsonify({'results': results})


@discovery_bp.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Get all devices from inventory"""
    devices = InventoryModel.get_all_devices(db)
    
    # Enrich with image regex
    for device in devices:
        device['image_regex'] = get_image_regex_for_model(device.get('model'))
        
    return jsonify({'devices': devices})


@discovery_bp.route('/api/inventory/clear', methods=['DELETE'])
def clear_inventory():
    """Clear all inventory, jobs, pre-checks, and logs"""
    # 1. Clear Jobs
    JobsModel.clear_all(db)
    
    # 2. Clear Pre-checks
    PreChecksModel.clear_all(db)
    
    # 3. Clear Inventory
    success = InventoryModel.clear_all(db)
    
    # 4. Clear Log Files
    try:
        config = get_config()
        logs_path = config.get('logs', {}).get('path', 'app/logs')
        # Handle relative path
        if not os.path.isabs(logs_path):
            logs_path = os.path.join(os.getcwd(), logs_path)
            
        if os.path.exists(logs_path):
            files = glob.glob(os.path.join(logs_path, '*.log'))
            for f in files:
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Error deleting log file {f}: {e}")
    except Exception as e:
        print(f"Error clearing logs: {e}")

    if success:
        return jsonify({'message': 'System cleared successfully (Inventory, Jobs, Logs)'})
    else:
        return jsonify({'error': 'Failed to clear inventory'}), 500
