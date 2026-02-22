"""
Shared Event Bus for Server-Sent Events (SSE)
Allows different parts of the application to broadcast messages to the frontend.
"""

import json
from typing import Dict, List, Any
from collections import deque

# Global event queue (capped to prevent unbounded memory growth)
# Stores dictionaries: {'job_id': str, 'message': str, 'timestamp': str}
event_queue: deque = deque(maxlen=10000)

def emit_job_log(job_id: str, message: str):
    """
    Add a job log message to the event queue.
    """
    event = {
        'type': 'job_log',
        'job_id': job_id,
        'message': message,
        'timestamp': None # Timestamp added by frontend or helper if needed
    }
    event_queue.append(event)

def get_events(start_index: int = 0) -> List[Dict[str, Any]]:
    """
    Get events starting from a specific index.
    """
    if start_index >= len(event_queue):
        return []
    return list(event_queue)[start_index:]
