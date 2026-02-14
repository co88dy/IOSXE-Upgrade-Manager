"""
IOS-XE Upgrade Manager - Main Flask Application
"""

from flask import Flask, render_template
from app.blueprints.discovery import discovery_bp
from app.blueprints.repository import repository_bp
from app.blueprints.upgrade import upgrade_bp
from app.blueprints.settings import settings_bp
from app.blueprints.bulk_ops import bulk_ops_bp
from app.blueprints.jobs import jobs_bp
from app.blueprints.install_remove_inactive import install_bp
from app.blueprints.copy_image import copy_image_bp
from app.blueprints.verify_image import verify_image_bp
from app.blueprints.reports import reports_bp
from app.blueprints.models import models_bp
from app.database.models import Database
import json
import os

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Initialize Flask app
app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')
app.config['SECRET_KEY'] = 'ios-xe-upgrade-manager-secret-key'
# No file size limit - IOS-XE images can be large
app.config['MAX_CONTENT_LENGTH'] = None

# Register blueprints
app.register_blueprint(discovery_bp)
app.register_blueprint(repository_bp)
app.register_blueprint(upgrade_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(bulk_ops_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(install_bp)
app.register_blueprint(copy_image_bp)
app.register_blueprint(verify_image_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(models_bp)

# Initialize database
db_path = config['database']['path']
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db = Database(db_path)

# Create repository directory
os.makedirs(config['repository']['path'], exist_ok=True)


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/repo')
def repository_page():
    """Image repository page"""
    return render_template('repository.html')


@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'IOS-XE Upgrade Manager'}


def run_scheduler():
    """Background scheduler to check for pending jobs"""
    import time
    from datetime import datetime
    from app.database.models import JobsModel, InventoryModel
    # Import here to avoid circular import during app initialization
    from app.blueprints.upgrade import execute_upgrade
    
    print("Scheduler thread started...")
    
    while True:
        try:
            # Check every 30 seconds
            time.sleep(30)
            
            # Simple query - would be better in model
            # For now, get all scheduled jobs and filter in python
            # In a real app, use a proper DB query
            connection = db.get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT job_id, target_ip, target_version, schedule_time, log_file_path FROM jobs WHERE status = 'Scheduled'")
            scheduled_jobs = cursor.fetchall()
            connection.close()
            
            now = datetime.now()
            
            for job in scheduled_jobs:
                job_id = job['job_id']
                target_ip = job['target_ip']
                schedule_time_str = job['schedule_time']
                
                if schedule_time_str:
                    try:
                        schedule_time = datetime.fromisoformat(schedule_time_str)
                        # Ensure offset-naive/aware compatibility
                        if schedule_time.tzinfo is not None and now.tzinfo is None:
                            # Convert now to aware or schedule to naive
                            now_aware = now.astimezone() # Local time with timezone
                            # Actually, simpler to just compare timestamps or ensure both are one way
                            # Let's try to match them. 
                            # If schedule time is aware, use aware now.
                            check_time = now.astimezone() if schedule_time.tzinfo else now
                        elif schedule_time.tzinfo is None and now.tzinfo is not None:
                             check_time = now.replace(tzinfo=None)
                        else:
                             check_time = now

                        print(f"Checking Job {job_id}: Scheduled {schedule_time} <= Now {check_time}?")

                        if schedule_time <= check_time:
                            print(f"Triggering scheduled upgrade for {target_ip} (Job {job_id})")
                            
                            # Get device role for execute_upgrade
                            device = InventoryModel.get_device(db, target_ip)
                            device_role = device['device_role'] if device else 'Access'

                            # We need image_filename. It's not in jobs table usually, 
                            # but we need it for execute_upgrade. 
                            # Phase 7 refactor might have stored it? 
                            # upgrade.py schedule_upgrade received it. 
                            # We should probably store it in the job or infer it?
                            # For now, let's assume target_version IS the filename or look it up from Inventory target_image
                            # The frontend sends 'image_filename' as 'target_image' in payload.
                            # Inventory has 'target_image'. USE THAT.
                            image_filename = device['target_image'] if device else ''
                            
                            if image_filename:
                                log_file_path = job['log_file_path'] if 'log_file_path' in job.keys() else None
                                
                                thread = threading.Thread(
                                    target=execute_upgrade,
                                    args=(job_id, target_ip, image_filename, device_role, log_file_path)
                                )
                                thread.start()
                            else:
                                print(f"Error: No target image found for scheduled job {job_id}")
                                JobsModel.update_job_status(db, job_id, 'Failed', datetime.now())
                                
                    except ValueError:
                        print(f"Invalid date format for job {job_id}")
                        
        except Exception as e:
            print(f"Scheduler error: {e}")


if __name__ == '__main__':
    host = config['flask']['host']
    port = config['flask']['port']
    debug = config['flask']['debug']
    
    # Start scheduler thread
    import threading
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║       IOS-XE Upgrade Manager - Starting Server           ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  URL: http://{host}:{port}                          ║
    ║  Database: {db_path}                    ║
    ║  Repository: {config['repository']['path']}                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    app.run(host=host, port=port, debug=debug, threaded=True)
