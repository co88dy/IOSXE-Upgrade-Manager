"""
Shared extensions module for IOS-XE Upgrade Manager.
Provides a single Database instance and config helper
to avoid duplicate initialization across blueprints.
"""

import json
from app.database.models import Database


def get_config():
    """Reload and return config from disk (always fresh)"""
    with open('config.json', 'r') as f:
        return json.load(f)


# Single shared Database instance
_config = get_config()
db = Database(_config['database']['path'])
