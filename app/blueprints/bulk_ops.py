"""
Bulk operations blueprint for multi-device actions
"""

from flask import Blueprint, request, jsonify
from app.database.models import InventoryModel, PreChecksModel, RepositoryModel
import os
from app.utils.ssh_client import SSHClient
from app.utils.job_manager import JobManager
from app.extensions import db, get_config
import json

bulk_ops_bp = Blueprint('bulk_ops', __name__)

# Load config
config = get_config()
job_manager = JobManager(config['database']['path'], config['logs']['path'])


@bulk_ops_bp.route('/api/prechecks', methods=['POST'])
def run_prechecks():
    """
    Run prechecks on multiple devices
    Request body: {"ip_list": ["10.10.20.1", "10.10.20.2"]}
    """
    data = request.get_json()
    ip_list = data.get('ip_list', [])
    
    if not ip_list:
        return jsonify({'success': False, 'message': 'No IP addresses provided'}), 400
    
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    netconf_port = config['credentials']['netconf_port']
    
    results = []
    
    # 1. Validation Phase
    missing_target = []
    for ip in ip_list:
        device = InventoryModel.get_device(db, ip)
        if not device:
            continue # Should maybe error? But stick to target image focus
        if not device.get('target_image'):
            missing_target.append(ip)
            
    if missing_target:
        return jsonify({
            'success': False, 
            'message': f"Target Image not set for: {', '.join(missing_target)}. Please select a target image before running pre-checks."
        }), 400

    from app.utils.precheck_engine import PreCheckEngine
    from app.utils.netconf_client import NetconfClient
    
    # 2. Execution Phase
    for ip in ip_list:
        try:
            device = InventoryModel.get_device(db, ip)
            if not device:
                 results.append({'ip': ip, 'status': 'Fail', 'details': 'Device not found in inventory'})
                 continue

            # Target image is guaranteed by validation above
            target_image = device.get('target_image')

            # Run PreCheckEngine
            PreChecksModel.clear_checks_for_device(db, ip)
            precheck = PreCheckEngine(ip, username, password, netconf_port, enable_password)
            
            # Determine filesystem
            netconf_client = NetconfClient(ip, netconf_port, username, password)
            filesystem = netconf_client.get_filesystem_for_role(device['device_role'])
            
            # We need a target_version for checking. 
            # If target_image is set, try to extract it, or use "Unknown" if not.
            # The PreCheckEngine handles version comparison slightly differently now, 
            # but usually it needs `target_version` string.
            # Let's try to extract it from filename or inventory if we stored it?
            # Storing target_version in inventory would be ideal but currently we only have target_image (filename).
            # We can try to extract it similar to how the old code did, or just pass the filename as target_version for now?
            # Actually, PreCheckEngine requires `target_version`.
            # Let's extract it.
            # Get target image size from repository
            target_image_size_mb = 0
            image_details = RepositoryModel.get_image_details(db, target_image)
            if image_details and image_details.get('file_path') and os.path.exists(image_details['file_path']):
                size_bytes = os.path.getsize(image_details['file_path'])
                target_image_size_mb = size_bytes / (1024 * 1024)
            
            # Extract version from filename (handling k9. prefix)
            import re
            target_version = "Unknown"
            # Regex Explanation:
            # (?:k9\.|universalk9\.)?  -> Optional non-capturing group for 'k9.' or 'universalk9.' prefix
            # (\d+\.\d+\.\d+[a-z]?)    -> Capture group 1: Version number (digits.digits.digits + optional letter)
            ver_match = re.search(r'(?:k9\.|universalk9\.)?(\d+\.\d+\.\d+[a-z]?)', target_image)
            if ver_match:
                target_version = ver_match.group(1)

            check_results = precheck.run_all_checks(
                current_version=device['current_version'],
                target_version=target_version,
                device_role=device['device_role'],
                filesystem=filesystem,
                target_image_filename=target_image,
                target_image_size_mb=target_image_size_mb
            )
            
            # Auto-update image status if Image Presence passed
            for res in check_results:
                if res['check_name'] == 'Image Presence':
                    if res['result'] == 'PASS':
                        InventoryModel.set_image_copied(db, ip, 'Yes')
                    elif res['result'] == 'FAIL':
                         InventoryModel.set_image_copied(db, ip, 'No')
                         InventoryModel.set_image_verified(db, ip, 'No')

            # Store results
            for res in check_results:
                PreChecksModel.add_check(db, ip, res['check_name'], res['result'], res['message'])
            
            # Determine overall status
            all_passed = precheck.all_checks_passed()
            has_warnings = any(r['result'] == 'WARN' for r in check_results)
            
            status = 'Pass'
            if not all_passed:
                status = 'Fail'
            elif has_warnings:
                status = 'Warning'
                
            # Collect failure/warning details for the summary result
            details = []
            for res in check_results:
                if res['result'] in ['FAIL', 'WARN']:
                     details.append(f"{res['check_name']}: {res['message']}")
            
            details_str = '; '.join(details) if details else None
            
            # Update device inventory status
            # Re-fetch or update existing dict to avoid overwriting changes made above
            device_data = dict(device)
            device_data['precheck_status'] = status
            device_data['precheck_details'] = details_str
            
            # Ensure we don't overwrite the image status we just set
            # Check results again to set local dict values
            for res in check_results:
                if res['check_name'] == 'Image Presence':
                     if res['result'] == 'PASS':
                         device_data['image_copied'] = 'Yes'
                     elif res['result'] == 'FAIL':
                         device_data['image_copied'] = 'No'
                         device_data['image_verified'] = 'No'

            InventoryModel.add_device(db, device_data)
            
            results.append({
                'ip': ip,
                'status': status,
                'details': details
            })

        except Exception as e:
            results.append({
                'ip': ip,
                'status': 'Fail',
                'details': [str(e)]
            })
    
    return jsonify({
        'success': True,
        'results': results
    })


@bulk_ops_bp.route('/api/rediscover', methods=['POST'])
def rediscover_devices():
    """
    Re-discover devices to refresh their information
    Request body: {"ip_list": ["10.10.20.1", "10.10.20.2"]}
    """
    data = request.get_json()
    ip_list = data.get('ip_list', [])
    
    if not ip_list:
        return jsonify({'success': False, 'message': 'No IP addresses provided'}), 400
    
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    
    results = []
    
    for ip in ip_list:
        try:
            ssh = SSHClient(ip, username, password, enable_password)
            if ssh.connect():
                version_info = ssh.get_version_info()
                netconf_state = ssh.check_netconf_status()
                boot_var = ssh.get_boot_variables()
                free_space = ssh.get_free_space_mb()
                
                if version_info:
                    device_data = {
                        'ip_address': ip,
                        'hostname': version_info.get('hostname', 'Unknown'),
                        'serial_number': version_info.get('serial_number', 'Unknown'),
                        'device_role': 'Unknown',
                        'current_version': version_info.get('version', 'Unknown'),
                        'rommon_version': version_info.get('rommon_version', 'N/A'),
                        'config_register': version_info.get('config_register', 'Unknown'),
                        'status': 'Online',
                        'netconf_state': netconf_state,
                        'model': version_info.get('model', 'Unknown'),
                        'boot_variable': boot_var,
                        'free_space_mb': free_space,
                        'image_file': version_info.get('image_file'),
                        # Preserve existing precheck and image status
                        'precheck_status': None,
                        'precheck_details': None,
                        'target_image': None,
                        'image_copied': 'No',
                        'image_verified': 'No',
                        'is_supported': 'Yes'
                    }
                    
                    # Merge existing device fields to avoid data loss
                    existing = InventoryModel.get_device(db, ip)
                    if existing:
                        device_data['precheck_status'] = existing.get('precheck_status')
                        device_data['precheck_details'] = existing.get('precheck_details')
                        device_data['target_image'] = existing.get('target_image')
                        device_data['image_copied'] = existing.get('image_copied', 'No')
                        device_data['image_verified'] = existing.get('image_verified', 'No')
                        device_data['is_supported'] = existing.get('is_supported', 'Yes')
                        device_data['device_role'] = existing.get('device_role', 'Unknown')
                        
                        # Preserve config_register if SSH fallback didn't catch it
                        if device_data.get('config_register') == 'Unknown':
                            device_data['config_register'] = existing.get('config_register', 'Unknown')
                    
                    InventoryModel.add_device(db, device_data)
                    results.append({'ip': ip, 'status': 'success'})
                else:
                    results.append({'ip': ip, 'status': 'failed', 'error': 'Could not retrieve version info'})
                
                ssh.disconnect()
            else:
                results.append({'ip': ip, 'status': 'failed', 'error': 'Could not connect'})
        except Exception as e:
            results.append({'ip': ip, 'status': 'failed', 'error': str(e)})
    
    return jsonify({
        'success': True,
        'results': results
    })


@bulk_ops_bp.route('/api/devices/<ip>/set-target', methods=['POST'])
def set_target_image(ip):
    """
    Set target image for a device
    Request body: {"target_image": "c9300-universalk9.17.12.01.SPA.bin"}
    """
    data = request.get_json()
    target_image = data.get('target_image', '')
    
    if not target_image:
        return jsonify({'error': 'Target image is required'}), 400
    
    # Update database
    success = InventoryModel.set_target_image(db, ip, target_image)
   
    if success:
        return jsonify({
            'message': 'Target image set successfully',
            'device_ip': ip,
            'target_image': target_image
        })
    else:
        return jsonify({'error': 'Failed to set target image'}), 500


# Superseded by copy_image.py and verify_image.py
