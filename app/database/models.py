"""
Database models for IOS-XE Upgrade Manager
SQLite schema definitions for Inventory, Repository, Jobs, and PreChecks
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def _add_column_if_not_exists(self, cursor, table: str, column: str, column_type: str):
        """Add column to table if it doesn't exist"""
        try:
            cursor.execute(f'SELECT {column} FROM {table} LIMIT 1')
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}')
            print(f"Added column {column} to {table}")
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Inventory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                ip_address TEXT PRIMARY KEY,
                hostname TEXT,
                serial_number TEXT,
                device_role TEXT,
                current_version TEXT,
                rommon_version TEXT,
                config_register TEXT,
                status TEXT DEFAULT 'Offline',
                netconf_state TEXT DEFAULT 'Disabled',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_file TEXT
            )
        ''')
        
        # Add new columns if they don't exist (migration)
        self._add_column_if_not_exists(cursor, 'inventory', 'model', 'TEXT')
        self._add_column_if_not_exists(cursor, 'inventory', 'boot_variable', 'TEXT')
        self._add_column_if_not_exists(cursor, 'inventory', 'free_space_mb', 'INTEGER')
        self._add_column_if_not_exists(cursor, 'inventory', 'precheck_status', 'TEXT')
        self._add_column_if_not_exists(cursor, 'inventory', 'precheck_details', 'TEXT')
        self._add_column_if_not_exists(cursor, 'inventory', 'is_supported', 'TEXT DEFAULT "Yes"')
        self._add_column_if_not_exists(cursor, 'inventory', 'config_register', 'TEXT')
        
        # Repository table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repository (
                filename TEXT PRIMARY KEY,
                md5_expected TEXT,
                file_path TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                target_ip TEXT,
                job_type TEXT DEFAULT 'UPGRADE',
                target_version TEXT,
                schedule_time TIMESTAMP,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'Pending',
                log_file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (target_ip) REFERENCES inventory(ip_address)
            )
        ''')

        # Add new columns if they don't exist (migration for jobs)
        self._add_column_if_not_exists(cursor, 'jobs', 'job_type', 'TEXT')
        self._add_column_if_not_exists(cursor, 'jobs', 'start_time', 'TIMESTAMP')
        self._add_column_if_not_exists(cursor, 'jobs', 'end_time', 'TIMESTAMP')
        self._add_column_if_not_exists(cursor, 'jobs', 'log_file_path', 'TEXT')
        self._add_column_if_not_exists(cursor, 'jobs', 'scheduled_time', 'TEXT')
        self._add_column_if_not_exists(cursor, 'jobs', 'timezone', 'TEXT')
        self._add_column_if_not_exists(cursor, 'jobs', 'cancelled', 'INTEGER DEFAULT 0')
        
        # Add image_file column to inventory if it doesn't exist
        self._add_column_if_not_exists(cursor, 'inventory', 'image_file', 'TEXT')
        
        # Phase 2 migrations: Add target image and copy/verify status columns
        self._add_column_if_not_exists(cursor, 'inventory', 'target_image', 'TEXT')
        self._add_column_if_not_exists(cursor, 'inventory', 'image_copied', 'TEXT DEFAULT "No"')
        self._add_column_if_not_exists(cursor, 'inventory', 'image_verified', 'TEXT DEFAULT "No"')
        
        # Add md5_hash column to repository table
        self._add_column_if_not_exists(cursor, 'repository', 'md5_hash', 'TEXT')
        
        # PreChecks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prechecks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT,
                check_name TEXT,
                result TEXT,
                message TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ip_address) REFERENCES inventory(ip_address)
            )
        ''')
        
        conn.commit()
        conn.close()


class InventoryModel:
    """Inventory table operations"""
    
    @staticmethod
    def add_device(db: Database, device_data: Dict[str, Any]) -> bool:
        """Add or update device in inventory"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO inventory (
                    ip_address, hostname, serial_number, device_role, 
                    current_version, rommon_version, status, netconf_state, 
                    model, boot_variable, free_space_mb, precheck_status, precheck_details, image_file,
                    target_image, image_copied, image_verified, is_supported, config_register
                ) VALUES (
                    :ip_address, :hostname, :serial_number, :device_role,
                    :current_version, :rommon_version, :status, :netconf_state,
                    :model, :boot_variable, :free_space_mb, :precheck_status, :precheck_details, :image_file,
                    :target_image, :image_copied, :image_verified, :is_supported, :config_register
                )
            ''', device_data)
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding device: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_all_devices(db: Database) -> List[Dict[str, Any]]:
        """Get all devices from inventory"""
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM inventory ORDER BY ip_address')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_device(db: Database, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get single device by IP"""
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM inventory WHERE ip_address = ?', (ip_address,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    
    @staticmethod
    def update_netconf_state(db: Database, ip_address: str, state: str) -> bool:
        """Update NETCONF state for device"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE inventory SET netconf_state = ? WHERE ip_address = ?',
                (state, ip_address)
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating NETCONF state: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_target_image(db: Database, ip_address: str) -> Optional[str]:
        """Get target image for device"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT target_image FROM inventory WHERE ip_address = ?', (ip_address,))
            row = cursor.fetchone()
            if row:
                return row['target_image']
            return None
        except sqlite3.Error as e:
            print(f"Error getting target image: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def set_target_image(db: Database, ip_address: str, target_image: str) -> bool:
        """Set target image for device"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            # Check if device exists first
            cursor.execute('SELECT 1 FROM inventory WHERE ip_address = ?', (ip_address,))
            if not cursor.fetchone():
                return False
                
            cursor.execute('''
                UPDATE inventory 
                SET target_image = ?, image_copied = 'No', image_verified = 'No', last_updated = CURRENT_TIMESTAMP 
                WHERE ip_address = ?
            ''', (target_image, ip_address))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error setting target image: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def set_image_copied(db: Database, ip_address: str, status: str = 'Yes') -> bool:
        """Set image copied status"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE inventory 
                SET image_copied = ?, last_updated = CURRENT_TIMESTAMP 
                WHERE ip_address = ?
            ''', (status, ip_address))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error setting image copied status: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def set_image_verified(db: Database, ip_address: str, status: str = 'Yes') -> bool:
        """Set image verified status"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE inventory 
                SET image_verified = ?, last_updated = CURRENT_TIMESTAMP 
                WHERE ip_address = ?
            ''', (status, ip_address))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error setting image verified status: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def clear_all(db: Database) -> bool:
        """Clear all inventory entries"""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM inventory')
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing inventory: {e}")
            return False
        finally:
            conn.close()


class RepositoryModel:
    """Repository table operations"""
    
    @staticmethod
    def add_image(db: Database, filename: str, md5: str, file_path: str) -> bool:
        """Add image to repository"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO repository (filename, md5_expected, file_path)
                VALUES (?, ?, ?)
            ''', (filename, md5, file_path))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding image: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_all_images(db: Database) -> List[Dict[str, Any]]:
        """Get all images from repository"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM repository ORDER BY upload_date DESC')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error getting images: {e}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    def get_image_hash(db: Database, filename: str) -> Optional[str]:
        """Get expected MD5 hash for image"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT md5_expected FROM repository WHERE filename = ?', (filename,))
            row = cursor.fetchone()
            if row:
                return row['md5_expected']
            return None
        except sqlite3.Error as e:
            print(f"Error getting image hash: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def delete_image(db: Database, filename: str) -> bool:
        """Delete image from repository"""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM repository WHERE filename = ?', (filename,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting image: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def get_image_details(db: Database, filename: str) -> Optional[Dict[str, Any]]:
        """Get image details including file path"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM repository WHERE filename = ?', (filename,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting image details: {e}")
            return None
        finally:
            conn.close()


class JobsModel:
    """Jobs table operations"""
    
    @staticmethod
    def create_job(db: Database, job_data: Dict[str, Any]) -> bool:
        """Create new job"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO jobs (job_id, target_ip, job_type, target_version, schedule_time, start_time, status, log_file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_data.get('job_id'),
                job_data.get('target_ip'),
                job_data.get('job_type', 'UPGRADE'),
                job_data.get('target_version'),
                job_data.get('schedule_time'),
                job_data.get('start_time'),
                job_data.get('status', 'Pending'),
                job_data.get('log_file_path')
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error creating job: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def update_job_status(db: Database, job_id: str, status: str, end_time: datetime = None) -> bool:
        """Update job status and end time"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            if end_time:
                cursor.execute(
                    'UPDATE jobs SET status = ?, end_time = ? WHERE job_id = ?',
                    (status, end_time, job_id)
                )
            else:
                cursor.execute(
                    'UPDATE jobs SET status = ? WHERE job_id = ?',
                    (status, job_id)
                )
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating job: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def cancel_job(db: Database, job_id: str) -> bool:
        """Cancel a job (update status to Cancelled)"""
        return JobsModel.update_job_status(db, job_id, 'Cancelled')

    @staticmethod
    def delete_job(db: Database, job_id: str) -> bool:
        """Delete a job permanently"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting job: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def update_job_schedule(db: Database, job_id: str, schedule_time: str) -> bool:
        """Update job schedule time"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE jobs SET schedule_time = ?, status = ? WHERE job_id = ?',
                (schedule_time, 'Scheduled', job_id)
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating job schedule: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_all_jobs(db: Database) -> List[Dict[str, Any]]:
        """Get all jobs"""
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT jobs.*, inventory.hostname 
            FROM jobs 
            LEFT JOIN inventory ON jobs.target_ip = inventory.ip_address 
            ORDER BY jobs.created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_job(db: Database, job_id: str) -> Optional[Dict[str, Any]]:
        """Get single job by ID"""
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
        
    @staticmethod
    def get_scheduled_jobs(db: Database) -> List[Dict[str, Any]]:
        """Get all scheduled jobs"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id, target_ip, target_version, schedule_time, log_file_path FROM jobs WHERE status = 'Scheduled'")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error getting scheduled jobs: {e}")
            return []
        finally:
            conn.close()
            
    @staticmethod
    def get_active_jobs_for_device(db: Database, ip_address: str) -> List[Dict[str, Any]]:
        """Get active jobs for a specific device"""
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE target_ip = ? AND status = 'RUNNING'", (ip_address,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_active_jobs(db: Database) -> List[Dict[str, Any]]:
        """Get all active (RUNNING) jobs"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE status = 'RUNNING' ORDER BY start_time DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error getting active jobs: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_jobs_for_device(db: Database, ip_address: str) -> List[Dict[str, Any]]:
        """Get recent jobs for a specific device"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE target_ip = ? ORDER BY start_time DESC LIMIT 10", (ip_address,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error getting jobs for device: {e}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    def clear_all(db: Database) -> bool:
        """Clear all jobs"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM jobs')
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing jobs: {e}")
            return False
        finally:
            conn.close()


class PreChecksModel:
    """PreChecks table operations"""
    
    @staticmethod
    def add_check(db: Database, ip_address: str, check_name: str, result: str, message: str) -> bool:
        """Add pre-check result"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO prechecks (ip_address, check_name, result, message)
                VALUES (?, ?, ?, ?)
            ''', (ip_address, check_name, result, message))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding pre-check: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_checks_for_device(db: Database, ip_address: str) -> List[Dict[str, Any]]:
        """Get all pre-checks for a device"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM prechecks WHERE ip_address = ? ORDER BY checked_at DESC',
                (ip_address,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error getting checks: {e}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    def clear_all(db: Database) -> bool:
        """Clear all pre-checks"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM prechecks')
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing pre-checks: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def clear_checks_for_device(db: Database, ip_address: str) -> bool:
        """Clear pre-checks for a device"""
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM prechecks WHERE ip_address = ?', (ip_address,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing pre-checks: {e}")
            return False
        finally:
            conn.close()
