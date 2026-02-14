"""
Blueprint for handling image verification operations.
Spawns individual jobs per device for MD5 checksum validation.
"""

from flask import Blueprint, request, jsonify
from app.database.models import Database, InventoryModel, JobsModel, RepositoryModel
from app.utils.ssh_client import SSHClient
from app.utils.job_manager import JobManager
import json
import threading
import uuid
from datetime import datetime

verify_image_bp = Blueprint('verify_image', __name__)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

db = Database(config['database']['path'])
job_manager = JobManager(config['database']['path'], config['logs']['path'])


@verify_image_bp.route('/api/operations/verify', methods=['POST'])
def start_verify_job():
    """
    Start image verification job for multiple devices.
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

        # Create Job ID
        job_id = str(uuid.uuid4())
        job_ids.append(job_id)

        # Create Job Logger
        log_file_path = job_manager.create_job_logger(job_id)

        # Create Job Record
        JobsModel.create_job(db, {
            'job_id': job_id,
            'target_ip': ip,
            'target_version': 'N/A', # Image copy doesn't necessarily have a version yet
            'job_type': 'IMAGE_VERIFY',
            'status': 'Pending',
            'schedule_time': datetime.now().isoformat(),
            'log_file_path': log_file_path
        })

        # Start Background Thread
        thread = threading.Thread(
            target=execute_verify_job,
            args=(job_id, ip, target_image)
        )
        thread.daemon = True
        thread.start()

    return jsonify({
        'success': True,
        'message': f'Started {len(job_ids)} verification jobs',
        'job_ids': job_ids
    })


def execute_verify_job(job_id, ip_address, image_filename):
    """
    Execute verify job for a single device
    """
    job_manager.update_job_status(job_id, "Running")
    job_manager.append_log(job_id, f"Stack: Starting image verification for {ip_address}")
    
    try:
        # Reload config
        with open('config.json', 'r') as f:
            local_config = json.load(f)
            
        username = local_config['credentials']['ssh_username']
        password = local_config['credentials']['ssh_password']
        enable_password = local_config['credentials'].get('enable_password', '')

        # Connect
        job_manager.append_log(job_id, "Connecting via SSH...")
        ssh = SSHClient(ip_address, username, password, enable_password)
        
        if not ssh.connect():
            job_manager.append_log(job_id, "ERROR: SSH connection failed")
            job_manager.update_job_status(job_id, "Failed")
            return

        # Verification Logic
        destination_fs = "flash:" # Default
        
        job_manager.append_log(job_id, f"Verifying {image_filename} on {destination_fs}...")
        
        # Check if file exists first
        if not ssh.check_file_exists(destination_fs, image_filename):
            job_manager.append_log(job_id, f"❌ ERROR: File {image_filename} not found on {destination_fs}")
            InventoryModel.set_image_copied(db, ip_address, 'No')
            InventoryModel.set_image_verified(db, ip_address, 'Failed')
            job_manager.update_job_status(job_id, "Failed")
            ssh.disconnect()
            return

        # Get Expected Hash
        expected_hash = RepositoryModel.get_image_hash(db, image_filename)
        if not expected_hash:
            job_manager.append_log(job_id, "⚠️ WARNING: No hash found in repository for this image. Cannot verify integrity.")
            InventoryModel.set_image_verified(db, ip_address, 'No hash')
            job_manager.update_job_status(job_id, "Success") # Technically success as we did check presence
            ssh.disconnect()
            return
            
        job_manager.append_log(job_id, f"Expected MD5: {expected_hash}")
        job_manager.append_log(job_id, "Calculating remote MD5 hash (this may take a minute)...")
        
        # Define callback for real-time logging
        def log_callback(message):
            job_manager.append_log(job_id, message)

        actual_hash = ssh.calculate_md5(destination_fs, image_filename, callback=log_callback)
        
        if actual_hash:
            job_manager.append_log(job_id, f"Actual MD5:   {actual_hash}")
            
            if actual_hash.lower() == expected_hash.lower():
                job_manager.append_log(job_id, "✅ Verification Successful! Hashes match.")
                InventoryModel.set_image_verified(db, ip_address, 'Yes')
                InventoryModel.set_image_copied(db, ip_address, 'Yes') # Confirm copy status too
                result = True
            else:
                job_manager.append_log(job_id, "❌ Verification Failed: Hash mismatch")
                InventoryModel.set_image_verified(db, ip_address, 'Failed')
        else:
            job_manager.append_log(job_id, "❌ Verification Failed: Could not calculate hash")
            InventoryModel.set_image_verified(db, ip_address, 'Failed')

        if result:
            job_manager.append_log(job_id, f"✅ Verification successful! MD5 matches.")
            InventoryModel.set_image_verified(db, ip_address, 'Yes')
            job_manager.update_job_status(job_id, 'COMPLETED')
        else:
            job_manager.update_job_status(job_id, "Failed")

        ssh.disconnect()

    except Exception as e:
        job_manager.append_log(job_id, f"CRITICAL ERROR: {str(e)}")
        job_manager.update_job_status(job_id, "Failed")
