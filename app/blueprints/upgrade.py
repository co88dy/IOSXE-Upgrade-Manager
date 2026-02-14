"""
Upgrade blueprint for upgrade orchestration and scheduling
"""

from flask import Blueprint, request, jsonify
from app.database.models import Database, JobsModel, InventoryModel, PreChecksModel
from app.utils.precheck_engine import PreCheckEngine
from app.utils.ssh_client import SSHClient
from app.utils.netconf_client import NetconfClient
from app.utils.event_bus import emit_job_log
from app.utils.job_manager import JobManager
import json
import uuid
from datetime import datetime
import threading
import os

upgrade_bp = Blueprint('upgrade', __name__)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

db = Database(config['database']['path'])
logs_path = config.get('logs', {}).get('path', 'app/logs')
job_manager = JobManager(config['database']['path'], logs_path)


@upgrade_bp.route('/api/precheck', methods=['POST'])
def run_precheck():
    """
    Run pre-checks on target device
    Request body: {"ip_address": "10.10.20.1", "target_version": "17.9.1"}
    """
    data = request.get_json()
    ip_address = data.get('ip_address')
    target_version = data.get('target_version')
    
    if not ip_address or not target_version:
        return jsonify({'error': 'Missing ip_address or target_version'}), 400
    
    # Get device info from inventory
    device = InventoryModel.get_device(db, ip_address)
    if not device:
        return jsonify({'error': 'Device not found in inventory'}), 404
    
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    netconf_port = config['credentials']['netconf_port']
    
    # Clear previous pre-checks for this device
    PreChecksModel.clear_checks_for_device(db, ip_address)
    
    # Run pre-checks
    precheck = PreCheckEngine(ip_address, username, password, netconf_port, enable_password)
    
    # Determine filesystem based on device role
    netconf_client = NetconfClient(ip_address, netconf_port, username, password)
    filesystem = netconf_client.get_filesystem_for_role(device['device_role'])
    
    # Validated target_image logic
    target_image = device.get('target_image')
    if not target_image:
        return jsonify({'error': 'Target image not selected for this device. Please select an image in the Inventory table.'}), 400

    results = precheck.run_all_checks(
        current_version=device['current_version'],
        target_version=target_version,
        device_role=device['device_role'],
        filesystem=filesystem,
        target_image_filename=target_image
    )
    
    # Update image status based on pre-check results
    for result in results:
        if result['check_name'] == 'Image Presence':
            if result['result'] == 'PASS':
                InventoryModel.set_image_copied(db, ip_address, 'Yes')
            elif result['result'] == 'FAIL':
                InventoryModel.set_image_copied(db, ip_address, 'No')
                InventoryModel.set_image_verified(db, ip_address, 'No')
    
    # Store results in database
    for result in results:
        PreChecksModel.add_check(
            db,
            ip_address,
            result['check_name'],
            result['result'],
            result['message']
        )
    
    # Check if all passed
    all_passed = precheck.all_checks_passed()
    
    return jsonify({
        'ip_address': ip_address,
        'target_version': target_version,
        'all_passed': all_passed,
        'results': results
    })


@upgrade_bp.route('/api/prechecks/<ip_address>', methods=['GET'])
def get_prechecks(ip_address):
    """Get pre-checks and device info for a device"""
    checks = PreChecksModel.get_checks_for_device(db, ip_address)
    device = InventoryModel.get_device(db, ip_address)
    
    device_info = {}
    if device:
        try:
            device_info = dict(device)
        except:
            pass # Handle case where dict conversion fails or device is None
            
    return jsonify({
        'checks': checks, 
        'device': device_info
    })


import zoneinfo

@upgrade_bp.route('/api/upgrade/schedule', methods=['POST'])
def schedule_upgrade():
    """
    Schedule upgrade job
    Request body: {
        "ip_address": "10.10.20.1",
        "target_version": "17.9.1",
        "image_filename": "cat9k_iosxe.17.09.01.SPA.bin",
        "schedule_time": "2026-02-12T10:00:00",  # ISO format
        "timezone": "America/New_York" # Optional
    }
    """
    data = request.get_json()
    ip_address = data.get('ip_address')
    target_version = data.get('target_version')
    image_filename = data.get('image_filename')
    schedule_time = data.get('schedule_time')
    timezone = data.get('timezone', 'UTC')
    
    # Process schedule_time with timezone
    if schedule_time:
        try:
            # Parse naive time from string
            dt = datetime.fromisoformat(schedule_time)
            # Apply timezone
            tz = zoneinfo.ZoneInfo(timezone)
            # We use replace because the input is "Time in that timezone" 
            # not "Time in UTC that needs converting"
            dt = dt.replace(tzinfo=tz)
            schedule_time = dt.isoformat()
        except Exception as e:
            print(f"Error processing timezone {timezone}: {e}")
            # Fallback to naive/UTC if error
            pass
    
    if not all([ip_address, target_version, image_filename]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Get device info
    device = InventoryModel.get_device(db, ip_address)
    if not device:
        return jsonify({'error': 'Device not found in inventory'}), 404
    
    # Check if pre-checks passed
    # User requested ability to bypass pre-checks (2026-02-12)
    # prechecks = PreChecksModel.get_checks_for_device(db, ip_address)
    # if not prechecks:
    #     # Warning only
    #     pass 
    
    # Check for any FAIL or ERROR results - BYPASSING validation to allow override
    # for check in prechecks:
    #     if check['result'] in ['FAIL', 'ERROR']:
    #         # Warning only
    #         pass
    
    # Create job
    job_id = str(uuid.uuid4())
    
    # Create log file immediately using JobManager
    log_file_path = job_manager.create_job_logger(job_id)
    if not log_file_path:
         # Fallback if job_manager fails (unlikely)
         log_file_path = f"app/logs/{job_id}.log"
    
    # Determine job type
    job_type = 'UPGRADE'
    if not schedule_time:
        job_type = 'ON_DEMAND'
        
    job_data = {
        'job_id': job_id,
        'target_ip': ip_address,
        'job_type': job_type,
        'target_version': target_version,
        'schedule_time': schedule_time if schedule_time else datetime.now().isoformat(),
        'status': 'Scheduled' if schedule_time else 'Pending',
        'log_file_path': log_file_path
    }
    
    JobsModel.create_job(db, job_data)
    
    # If no schedule time, run immediately
    if not schedule_time:
        thread = threading.Thread(
            target=execute_upgrade,
            args=(job_id, ip_address, image_filename, device['device_role'], log_file_path)
        )
        thread.start()
    
    return jsonify({
        'message': 'Upgrade job created',
        'job_id': job_id,
        'status': 'Running' if not schedule_time else 'Scheduled'
    })


def execute_upgrade(job_id: str, ip_address: str, image_filename: str, device_role: str, log_file_path: str = None):
    """
    Execute upgrade in background thread
    """
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    netconf_port = config['credentials']['netconf_port']
    
    # Update job status
    JobsModel.update_job_status(db, job_id, 'Running')
    
    log_output = []
    
    # Initialize log file if provided
    if log_file_path:
        try:
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            with open(log_file_path, 'w') as f:
                f.write(f"Upgrade Log for Job {job_id}\n")
                f.write(f"Device: {ip_address}\n")
                f.write(f"Target: {image_filename}\n")
                f.write("-" * 50 + "\n")
        except Exception as e:
            print(f"Error creating log file: {e}")

    def log(message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        log_output.append(log_entry)
        emit_job_log(job_id, message)
        print(message)
        
        # Append to file
        if log_file_path:
            try:
                with open(log_file_path, 'a') as f:
                    f.write(log_entry + "\n")
            except:
                pass
    
    try:
        log(f"Starting upgrade for {ip_address}")
        
        # Determine filesystem
        netconf_client = NetconfClient(ip_address, netconf_port, username, password)
        filesystem = netconf_client.get_filesystem_for_role(device_role)
        
        log(f"Device role: {device_role}, Filesystem: {filesystem}")
        
        # Connect via SSH
        ssh = SSHClient(ip_address, username, password, enable_password)
        if not ssh.connect():
            log("ERROR: SSH connection failed")
            JobsModel.update_job_status(db, job_id, 'Failed', '\n'.join(log_output))
            return
        
        log("SSH connection established")

        # Verify file exists strictly before installing
        log(f"Verifying {image_filename} exists on {filesystem}...")
        if not ssh.check_file_exists(filesystem, image_filename):
             log(f"ERROR: Image file {image_filename} not found on {filesystem}. Please 'Copy Image' first.")
             JobsModel.update_job_status(db, job_id, 'Failed', '\n'.join(log_output))
             ssh.disconnect()
             return

        log("Image verification successful.")
        
        # Save configuration to prevent 'System configuration has been modified' error
        log("Saving system configuration...")
        if ssh.save_config():
            log("Configuration saved successfully.")
        else:
            log("Warning: Failed to save configuration. Upgrade might fail if config is modified.")
            
        log("Proceeding to Install mode upgrade...")
        
        # Execute install command
        # Command structure: install add file <filesystem>:<filename> activate commit prompt-level none
        log(f"Executing: install add file {filesystem}{image_filename} activate commit prompt-level none")
        
        # Use callback for real-time logging
        install_result = ssh.execute_install_command(filesystem, image_filename, callback=lambda msg: log(msg.strip()))
        
        if install_result.get('success'):
            if install_result.get('status') == 'RELOADING':
                log("Device is reloading as expected. Connection dropped.")
                log("Upgrade initiated successfully.")
            else:
                log("Install command completed successfully")
            
            JobsModel.update_job_status(db, job_id, 'Success', '\n'.join(log_output))
        else:
            log(f"ERROR: Install command failed - {install_result.get('error', 'Unknown error')}")
            JobsModel.update_job_status(db, job_id, 'Failed', '\n'.join(log_output))
        
        ssh.disconnect()
        log("Upgrade process completed")
        
    except Exception as e:
        log(f"EXCEPTION: {str(e)}")
        JobsModel.update_job_status(db, job_id, 'Failed', '\n'.join(log_output))
