"""
Install Blueprint for handling installation operations
"""

from flask import Blueprint, request, jsonify
from app.utils.ssh_client import SSHClient
from app.utils.job_manager import JobManager
from app.database.models import Database
import json
import threading
import time

install_bp = Blueprint('install', __name__)

# Load config
def get_config():
    with open('config.json', 'r') as f:
        return json.load(f)

@install_bp.route('/api/install-remove-inactive', methods=['POST'])
def install_remove_inactive():
    """
    Run 'install remove inactive' command on multiple devices (Async)
    Request body: {"ip_list": ["10.10.20.1", "10.10.20.2"]}
    """
    config = get_config()
    data = request.get_json()
    ip_list = data.get('ip_list', [])
    
    if not ip_list:
        return jsonify({'success': False, 'message': 'No IP addresses provided'}), 400
    
    username = config['credentials']['ssh_username']
    password = config['credentials']['ssh_password']
    enable_password = config['credentials'].get('enable_password', '')
    
    # Initialize JobManager
    logs_path = config.get('logs', {}).get('path', 'app/logs')
    job_manager = JobManager(config['database']['path'], logs_path)
    
    results = []
    
    for ip in ip_list:
        # Create job
        job_id = job_manager.start_job(ip, 'INSTALL_REMOVE_INACTIVE')
        
        if job_id:
            # Start background thread
            thread = threading.Thread(
                target=_run_install_remove_inactive_thread,
                args=(job_id, ip, username, password, enable_password, config['database']['path'], logs_path)
            )
            thread.daemon = True
            thread.start()
            
            results.append({
                'ip': ip,
                'status': 'started',
                'job_id': job_id
            })
        else:
            results.append({
                'ip': ip,
                'status': 'failed',
                'error': 'Could not create job'
            })
    
    return jsonify({
        'success': True,
        'results': results
    })

def _run_install_remove_inactive_thread(job_id, ip, username, password, enable_password, db_path, logs_path):
    """Background thread for install remove inactive with streaming"""
    job_manager = JobManager(db_path, logs_path)
    
    try:
        job_manager.append_log(job_id, f"Connecting to {ip}...")
        ssh = SSHClient(ip, username, password, enable_password)
        
        if ssh.connect():
            job_manager.append_log(job_id, "Connected. Running 'install remove inactive'...")
            
            # Define callback for streaming output and capturing valid output
            full_output = []
            def log_callback(data):
                clean_data = data.strip()
                full_output.append(clean_data)
                job_manager.append_log(job_id, clean_data)

            # Use new streaming method with prompt handling
            # Add handling for [y/n] confirmation if it appears
            prompts = {r'\[y/n\]': 'y'}
            
            success = ssh.execute_command_stream(
                'install remove inactive',
                callback=log_callback,
                prompts=prompts
            )
            
            # Join all output to check for errors
            output_str = "\n".join(full_output)
            
            # Check for common failure keywords in IOS-XE install commands
            failure_keywords = ['% Error', 'Failed', 'failure', 'Invalid']
            has_error = any(keyword.lower() in output_str.lower() for keyword in failure_keywords)
            
            if success and not has_error:
                job_manager.append_log(job_id, "Command completed successfully.")
                job_manager.update_job_status(job_id, 'COMPLETED')
            else:
                if has_error:
                    job_manager.append_log(job_id, "Command output indicates failure.")
                else:
                    job_manager.append_log(job_id, "Command execution failed or timed out.")
                job_manager.update_job_status(job_id, 'FAILED')
            
            ssh.disconnect()
        else:
            job_manager.append_log(job_id, "Failed to connect to device.")
            job_manager.update_job_status(job_id, 'FAILED')
            
    except Exception as e:
        job_manager.append_log(job_id, f"Error: {str(e)}")
        job_manager.update_job_status(job_id, 'FAILED')
