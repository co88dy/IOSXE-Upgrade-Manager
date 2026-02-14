"""
Jobs blueprint for managing and viewing background jobs
"""

from flask import Blueprint, request, jsonify
from app.database.models import Database, JobsModel
from app.utils.job_manager import JobManager
from app.utils.event_bus import event_queue, get_events
import json

jobs_bp = Blueprint('jobs', __name__)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

db = Database(config['database']['path'])
logs_path = config.get('logs', {}).get('path', 'app/logs')
job_manager = JobManager(config['database']['path'], logs_path)


@jobs_bp.route('/api/jobs', methods=['GET'])
def get_all_jobs():
    """Get all jobs"""
    jobs = JobsModel.get_all_jobs(db)
    return jsonify({'jobs': jobs})


@jobs_bp.route('/api/jobs/clear', methods=['DELETE'])
def clear_jobs():
    """Clear all jobs"""
    success = JobsModel.clear_all(db)
    if success:
        return jsonify({'message': 'Jobs cleared successfully'})
    else:
        return jsonify({'error': 'Failed to clear jobs'}), 500


@jobs_bp.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """
    Get job details and log content
    """
    job = job_manager.get_job_details(job_id)
    if job:
        return jsonify({
            'success': True,
            'job': job
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Job not found'
        }), 404


@jobs_bp.route('/api/jobs/active', methods=['GET'])
def get_active_jobs():
    """
    Get all active jobs (RUNNING status)
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE status = 'RUNNING' ORDER BY start_time DESC")
    rows = cursor.fetchall()
    conn.close()
    
    jobs = [dict(row) for row in rows]
    return jsonify({
        'success': True,
        'count': len(jobs),
        'jobs': jobs
    })


@jobs_bp.route('/api/jobs/device/<ip>', methods=['GET'])
def get_device_jobs(ip):
    """
    Get all jobs for a specific device
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE target_ip = ? ORDER BY start_time DESC LIMIT 10", (ip,))
    rows = cursor.fetchall()
    conn.close()
    
    jobs = [dict(row) for row in rows]
    return jsonify({
        'success': True,
        'jobs': jobs
    })


@jobs_bp.route('/api/events')
def stream_events():
    """
    Server-Sent Events endpoint for real-time logs
    Shared across all job types (copy, verify, upgrade, etc.)
    """
    def generate():
        # Start from the current end of queue to avoid replaying old history
        last_index = len(event_queue)
        
        while True:
            # Send new events
            events = get_events(last_index)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
                last_index += 1
            
            # Keep connection alive
            import time
            time.sleep(0.5)
    
    
    return generate(), {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    }


@jobs_bp.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a job"""
    success = JobsModel.cancel_job(db, job_id)
    if success:
        return jsonify({'success': True, 'message': 'Job cancelled successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to cancel job'}), 500


@jobs_bp.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete a job"""
    success = JobsModel.delete_job(db, job_id)
    if success:
        return jsonify({'success': True, 'message': 'Job deleted successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to delete job'}), 500


import zoneinfo
from datetime import datetime

@jobs_bp.route('/api/jobs/<job_id>/reschedule', methods=['POST'])
def reschedule_job(job_id):
    """Reschedule a job"""
    data = request.get_json()
    schedule_time = data.get('schedule_time')
    timezone = data.get('timezone', 'UTC')
    
    if not schedule_time:
        return jsonify({'success': False, 'message': 'Missing schedule_time'}), 400
        
    try:
        # Parse and localize
        dt = datetime.fromisoformat(schedule_time)
        tz = zoneinfo.ZoneInfo(timezone)
        dt = dt.replace(tzinfo=tz)
        schedule_time = dt.isoformat()
    except Exception as e:
        print(f"Error processing timezone {timezone}: {e}")
        # Fallback to naive/UTC if error
        pass
        
    success = JobsModel.update_job_schedule(db, job_id, schedule_time)
    if success:
        return jsonify({'success': True, 'message': 'Job rescheduled successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to reschedule job'}), 500
