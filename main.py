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
from apscheduler.schedulers.background import BackgroundScheduler

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Initialize Flask app
app = Flask(__name__, 
            template_folder='app/templates',
            static_folder='app/static')
# Initialize Scheduler
scheduler = BackgroundScheduler()
app.config['scheduler'] = scheduler
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


def check_scheduled_jobs():
    """Background task to check for pending jobs"""
    from datetime import datetime, timedelta
    import zoneinfo
    from app.database.models import JobsModel, InventoryModel
    from app.blueprints.upgrade import execute_upgrade
    
    # Jobs older than this threshold will be marked as Missed instead of executed
    STALE_THRESHOLD = timedelta(hours=1)
    
    try:
        scheduled_jobs = JobsModel.get_scheduled_jobs(db)
        now_utc = datetime.now(zoneinfo.ZoneInfo('UTC'))
        
        for job in scheduled_jobs:
            job_id = job['job_id']
            target_ip = job['target_ip']
            schedule_time_str = job['schedule_time']
            
            if schedule_time_str:
                try:
                    schedule_time = datetime.fromisoformat(schedule_time_str)
                    
                    if schedule_time <= now_utc:
                        # Check if the job is stale (past the threshold)
                        if (now_utc - schedule_time) > STALE_THRESHOLD:
                            print(f"Marking stale job {job_id} for {target_ip} as Missed "
                                  f"(scheduled for {schedule_time_str}, now {now_utc.isoformat()})")
                            JobsModel.update_job_status(db, job_id, 'Missed', datetime.now())
                            continue
                        
                        print(f"Triggering scheduled upgrade for {target_ip} (Job {job_id})")
                        
                        device = InventoryModel.get_device(db, target_ip)
                        device_role = device['device_role'] if device else 'Access'
                        image_filename = device['target_image'] if device else ''
                        
                        if image_filename:
                            log_file_path = job.get('log_file_path')
                            app.config['scheduler'].add_job(
                                id=f"upgrade_{job_id}",
                                func=execute_upgrade,
                                args=(job_id, target_ip, image_filename, device_role, log_file_path)
                            )
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
    
    # Start scheduler
    scheduler.add_job(func=check_scheduled_jobs, trigger="interval", seconds=30)
    scheduler.start()
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║       IOS-XE Upgrade Manager - Starting Server           ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  URL: http://{host}:{port}                          ║
    ║  Database: {db_path}                    ║
    ║  Repository: {config['repository']['path']}                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    try:
        app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
