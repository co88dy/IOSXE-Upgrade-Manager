"""
Blueprint for handling image copy operations.
Spawns individual jobs per device for better tracking and concurrency.
"""

from flask import Blueprint, request, jsonify
from app.database.models import Database, InventoryModel, JobsModel
from app.utils.ssh_client import SSHClient
from app.utils.job_manager import JobManager
from app.blueprints.verify_image import execute_verify_job
import json
import threading
import uuid
import re
from datetime import datetime

copy_image_bp = Blueprint('copy_image', __name__)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

db = Database(config['database']['path'])
job_manager = JobManager(config['database']['path'], config['logs']['path'])


@copy_image_bp.route('/api/operations/copy', methods=['POST'])
def start_copy_job():
    """
    Start image copy job for multiple devices.
    Creates a separate job for EACH device.
    Request body: {"ip_list": ["10.10.20.1", ...], "target_image": "optional_global_image.bin"}
    """
    data = request.get_json()
    ip_list = data.get('ip_list', [])
    global_target_image = data.get('target_image')

    if not ip_list:
        return jsonify({'error': 'No devices provided'}), 400

    job_ids = []

    for ip in ip_list:
        # Determine target image for this specific device
        target_image = global_target_image
        if not target_image:
            device = InventoryModel.get_device(db, ip)
            if device:
                target_image = device.get('target_image')
        
        if not target_image:
            # Skip this device if no image selected
            continue

        # Extract version from filename if possible
        target_version = 'N/A'
        if target_image:
            # Try to match typical IOS-XE version patterns (e.g. 17.09.05, 16.12.4, 17.3.1a)
            # Look for versions starting with 16 or 17 to avoid capturing '3k9' type strings
            # Matches 16.X.X or 17.X.X, optionally followed by letters
            version_match = re.search(r"(?:^|[^0-9])(1[6-7]\.\d+\.\d+[a-zA-Z0-9]*)", target_image)
            if version_match:
                target_version = version_match.group(1)

        # Create Job ID
        job_id = str(uuid.uuid4())
        job_ids.append(job_id)

        # Create Job Logger
        log_file_path = job_manager.create_job_logger(job_id)

        # Create Job Record
        JobsModel.create_job(db, {
            'job_id': job_id,
            'target_ip': ip,
            'target_version': target_version,
            'job_type': 'IMAGE_COPY',
            'status': 'Pending',
            'schedule_time': datetime.now().isoformat(),
            'log_file_path': log_file_path
        })

        # Start Background Thread
        thread = threading.Thread(
            target=execute_copy_job,
            args=(job_id, ip, target_image)
        )
        thread.daemon = True
        thread.start()

    return jsonify({
        'success': True,
        'message': f'Started {len(job_ids)} copy jobs',
        'job_ids': job_ids
    })


def execute_copy_job(job_id, ip_address, image_filename):
    """
    Execute copy job for a single device
    """
    job_manager.update_job_status(job_id, "Running")
    job_manager.append_log(job_id, f"Stack: Starting image copy for {ip_address}")
    
    try:
        # Reload config for latest settings
        with open('config.json', 'r') as f:
            local_config = json.load(f)
            
        username = local_config['credentials']['ssh_username']
        password = local_config['credentials']['ssh_password']
        enable_password = local_config['credentials'].get('enable_password', '')
        
        server_ip = local_config.get('http_server_ip', '127.0.0.1')
        # Use repository port if configured (e.g. 80 for Docker/Nginx), otherwise fallback to Flask port
        repo_port = local_config.get('repository', {}).get('http_port')
        server_port = repo_port if repo_port else local_config.get('flask', {}).get('port', 5000)

        # Connect
        job_manager.append_log(job_id, "Connecting via SSH...")
        ssh = SSHClient(ip_address, username, password, enable_password)
        
        if not ssh.connect():
            job_manager.append_log(job_id, "ERROR: SSH connection failed")
            job_manager.update_job_status(job_id, "Failed")
            return

        # Prepare Copy
        destination_fs = "flash:" # Default, could be improved with discovery data
        http_url = f"http://{server_ip}:{server_port}/repo/{image_filename}"
        
        job_manager.append_log(job_id, f"Checking if file {image_filename} already exists...")
        if ssh.check_file_exists(destination_fs, image_filename):
             job_manager.append_log(job_id, f"File {image_filename} already exists on {destination_fs}. Overwriting...")
             # We proceed to copy/overwrite as requested, or should we skip?
             # Usually 'Copy Image' implies intent to copy. 
             # The ssh_client.copy_file_from_http handles overwrite prompts.

        # Define callback for real-time logging
        def log_callback(message):
            job_manager.append_log(job_id, message)

        job_manager.append_log(job_id, f"Initiating copy from {http_url}...")
        
        # Execute copy with callback
        result = ssh.copy_file_from_http(http_url, destination_fs, callback=log_callback)
        
        if result['success']:
            # job_manager.append_log(job_id, f"Output: {result.get('output', '')}") # Already logged via callback
            job_manager.append_log(job_id, "✅ Copy successful!")
            
            # Verify file size/integrity check to ensure it's not a 0-byte file
            # (Basic check, full verification is separate)
            job_manager.append_log(job_id, "Verifying file presence...")
            import time
            time.sleep(2) # Give file system a moment to settle
            if ssh.check_file_exists(destination_fs, image_filename):
                 job_manager.append_log(job_id, "File confirmed present on filesystem.")
                 InventoryModel.set_image_copied(db, ip_address, 'Yes')
                 InventoryModel.set_image_verified(db, ip_address, 'No') # Reset verification
                 
                 # Chain Verification
                 ssh.disconnect() # Disconnect before verify starts its own connection
                 job_manager.append_log(job_id, "Starting verification phase...")
                 execute_verify_job(job_id, ip_address, image_filename)
                 return # Verify job handles status updates
            else:
                 job_manager.append_log(job_id, "❌ ERROR: File copy reported success but file not found!")
                 job_manager.update_job_status(job_id, "Failed")
        else:
            job_manager.append_log(job_id, f"❌ Copy failed: {result.get('error')}")
            job_manager.append_log(job_id, f"Output: {result.get('output')}")
            job_manager.update_job_status(job_id, "Failed")

        ssh.disconnect()

    except Exception as e:
        job_manager.append_log(job_id, f"CRITICAL ERROR: {str(e)}")
        job_manager.update_job_status(job_id, "Failed")
