"""
Job Manager for handling background operations and logging
"""

import uuid
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.database.models import Database, JobsModel

class JobManager:
    """Manages job lifecycle and logging"""
    
    def __init__(self, db_path: str, logs_path: str):
        self.db = Database(db_path)
        self.logs_path = logs_path
        
        # Ensure logs directory exists
        os.makedirs(self.logs_path, exist_ok=True)

    def create_job_logger(self, job_id: str) -> str:
        """
        Create a log file for a specific job and return its path.
        Does NOT create a database record (caller must do that).
        """
        log_file_path = os.path.join(self.logs_path, f"{job_id}.log")
        try:
            with open(log_file_path, 'w') as f:
                f.write(f"Job Log Initialized: {datetime.now()}\n")
                f.write("-" * 40 + "\n")
            return log_file_path
        except Exception as e:
            print(f"Error creating log file: {e}")
            return ""
        
    def start_job(self, target_ip: str, job_type: str, target_version: str = None) -> str:
        """
        Start a new job
        Returns: job_id
        """
        job_id = str(uuid.uuid4())
        start_time = datetime.now()
        log_file_path = os.path.join(self.logs_path, f"{job_id}.log")
        
        # Create empty log file
        with open(log_file_path, 'w') as f:
            f.write(f"Job started at {start_time}\n")
            f.write(f"Type: {job_type}\n")
            f.write(f"Target: {target_ip}\n")
            f.write("-" * 40 + "\n")
            
        job_data = {
            'job_id': job_id,
            'target_ip': target_ip,
            'job_type': job_type,
            'target_version': target_version,
            'schedule_time': start_time, # Using start time as schedule time for immediate jobs
            'start_time': start_time,
            'status': 'RUNNING',
            'log_file_path': log_file_path
        }
        
        if JobsModel.create_job(self.db, job_data):
            return job_id
        return None
        
    def update_job_status(self, job_id: str, status: str) -> bool:
        """Update job status"""
        end_time = datetime.now() if status in ['COMPLETED', 'FAILED'] else None
        return JobsModel.update_job_status(self.db, job_id, status, end_time)
        
    def append_log(self, job_id: str, message: str):
        """Append message to job log file"""
        # We need to look up the log path first
        job = JobsModel.get_job(self.db, job_id)
        if not job or not job.get('log_file_path'):
            return
            
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(job['log_file_path'], 'a') as f:
                f.write(f"[{timestamp}] {message}\n")
            
            # Broadcast to UI
            from app.utils.event_bus import emit_job_log
            emit_job_log(job_id, message)
            
        except Exception as e:
            print(f"Error writing to log for job {job_id}: {e}")
            
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and log content"""
        job = JobsModel.get_job(self.db, job_id)
        if not job:
            return None
            
        # Read log content
        log_content = ""
        if job.get('log_file_path') and os.path.exists(job['log_file_path']):
            try:
                with open(job['log_file_path'], 'r') as f:
                    log_content = f.read()
            except Exception as e:
                log_content = f"Error reading log file: {e}"
                
        # Return job details with log content
        result = dict(job)
        result['log_content'] = log_content
        return result
