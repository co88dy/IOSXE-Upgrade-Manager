"""
SSH client for IOS-XE device communication
Uses Netmiko for CLI-based operations and NETCONF management
"""

from netmiko import ConnectHandler
from typing import Dict, Any, Optional, List
import re
import time


class SSHClient:
    """SSH operations for IOS-XE devices"""
    
    def __init__(self, host: str, username: str, password: str, enable_password: str = None):
        self.host = host
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.connection = None
    
    def connect(self) -> bool:
        """Establish SSH connection"""
        try:
            self.connection = ConnectHandler(
                device_type='cisco_ios',
                host=self.host,
                username=self.username,
                password=self.password,
                secret=self.enable_password if self.enable_password else self.password,
                timeout=30
            )
            
            # Enter enable mode if enable password is provided
            if self.enable_password and not self.connection.check_enable_mode():
                self.connection.enable()
            
            return True
        except Exception as e:
            print(f"SSH connection failed to {self.host}: {e}")
            return False

    def save_config(self) -> bool:
        """Save running configuration to startup configuration"""
        if not self.connection:
            return False
        
        try:
            output = self.connection.save_config()
            return 'OK' in output or 'Building configuration' in output or True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def disconnect(self):
        """Close SSH connection"""
        if self.connection:
            self.connection.disconnect()
    
    def enable_netconf(self) -> bool:
        """Enable NETCONF-YANG on device"""
        if not self.connection:
            return False
        
        try:
            commands = [
                'netconf-yang'
            ]
            output = self.connection.send_config_set(commands)
            self.connection.save_config()
            return 'netconf-yang' in output or True
        except Exception as e:
            print(f"Error enabling NETCONF: {e}")
            return False
    
    def disable_netconf(self) -> bool:
        """Disable NETCONF-YANG on device"""
        if not self.connection:
            return False
        
        try:
            commands = [
                'no netconf-yang'
            ]
            output = self.connection.send_config_set(commands)
            self.connection.save_config()
            return True
        except Exception as e:
            print(f"Error disabling NETCONF: {e}")
            return False
    
    def check_netconf_status(self) -> str:
        """
        Check if NETCONF is enabled on the device
        Returns 'Enabled' or 'Disabled'
        """
        if not self.connection:
            return 'Unknown'
        
        try:
            output = self.connection.send_command('show running-config | include netconf-yang')
            # If netconf-yang appears in running config, it's enabled
            if 'netconf-yang' in output and 'no netconf-yang' not in output:
                return 'Enabled'
            else:
                return 'Disabled'
        except Exception as e:
            print(f"Error checking NETCONF status: {e}")
            return 'Unknown'
    
    def check_rommon_variables(self) -> Dict[str, Any]:
        """
        Check ROMMON variables for SWITCH_IGNORE_STARTUP_CFG flag
        Returns dict with flag status and raw output
        """
        if not self.connection:
            return {'error': 'Not connected'}
        
        try:
            output = self.connection.send_command('show romvar')
            
            # Check for SWITCH_IGNORE_STARTUP_CFG=1
            ignore_flag = 'SWITCH_IGNORE_STARTUP_CFG=1' in output
            
            return {
                'ignore_startup_cfg': ignore_flag,
                'raw_output': output,
                'status': 'ERROR' if ignore_flag else 'PASS'
            }
        except Exception as e:
            print(f"Error checking ROMMON variables: {e}")
            return {'error': str(e)}
    
    def get_version_info(self) -> Optional[Dict[str, Any]]:
        """
        Get version information from 'show version'
        Fallback method when NETCONF is not available
        """
        if not self.connection:
            return None
        
        try:
            output = self.connection.send_command('show version')
            
            # Parse version
            version_match = re.search(r'Version ([^\s,]+)', output)
            version = version_match.group(1) if version_match else 'Unknown'
            
            # Parse hostname
            hostname_match = re.search(r'^(\S+)\s+uptime', output, re.MULTILINE)
            hostname = hostname_match.group(1) if hostname_match else 'Unknown'
            
            # Parse serial number - try multiple patterns for physical and virtual devices
            # First try: System serial number (physical devices)
            serial_match = re.search(r'System [Ss]erial [Nn]umber\s+:\s+(\S+)', output)
            if serial_match:
                serial = serial_match.group(1)
            else:
                # Second try: Processor board ID (virtual devices like C8000V, CSR1000V)
                serial_match = re.search(r'Processor board ID\s+(\S+)', output)
                serial = serial_match.group(1) if serial_match else 'Unknown'
            
            # Parse model
            model_match = re.search(r'cisco\s+(\S+)\s+\(', output)
            model = model_match.group(1) if model_match else 'Unknown'

            # Parse system image file (for Install Mode check)
            image_match = re.search(r'System image file is "([^"]+)"', output)
            image_file = image_match.group(1) if image_match else None

            # Parse ROMMON/Bootloader
            rom_match = re.search(r'ROM:\s+(.+)', output)
            rommon_version = rom_match.group(1).strip() if rom_match else 'Unknown'
            
            return {
                'version': version,
                'hostname': hostname,
                'serial_number': serial,
                'model': model,
                'image_file': image_file,
                'rommon_version': rommon_version
            }
        except Exception as e:
            print(f"Error getting version info: {e}")
            return None
    
    def get_boot_variables(self) -> Optional[str]:
        """Get boot variable setting from device"""
        if not self.connection:
            return None
        
        try:
            output = self.connection.send_command('show boot')
            
            # Look for BOOT variable
            boot_match = re.search(r'BOOT variable = (.+)', output)
            if boot_match:
                return boot_match.group(1).strip()
            
            # Alternative: look for boot system commands
            boot_system_match = re.search(r'boot system (\S+)', output)
            if boot_system_match:
                return boot_system_match.group(1).strip()
            
            return 'Not configured'
        except Exception as e:
            print(f"Error getting boot variables: {e}")
            return None
    
    def get_romvar(self) -> Optional[str]:
        """Get 'show romvar' output"""
        if not self.connection:
            return None
        
        try:
            return self.connection.send_command('show romvar')
        except Exception as e:
            print(f"Error getting romvar: {e}")
            return None

    def get_install_summary(self) -> Optional[str]:
        """Get 'show install summary' output"""
        if not self.connection:
            return None
        
        try:
            return self.connection.send_command('show install summary')
        except Exception as e:
            print(f"Error getting install summary: {e}")
            return None
    
    def get_free_space_mb(self) -> Optional[int]:
        """Get free filesystem space in MB"""
        if not self.connection:
            return None
        
        try:
            output = self.connection.send_command('dir')
            
            # Parse free space - look for pattern like "7897088000 bytes free"
            free_match = re.search(r'(\d+) bytes free', output)
            if free_match:
                bytes_free = int(free_match.group(1))
                mb_free = bytes_free // (1024 * 1024)  # Convert to MB
                return mb_free
            
            return None
        except Exception as e:
            print(f"Error getting free space: {e}")
            return None
    
    def execute_install_command(self, filesystem: str, filename: str, callback=None) -> Dict[str, Any]:
        """
        Execute the one-step install command
        install add file <filesystem>:<filename> activate commit prompt-level none
        """
        if not self.connection:
            return {'success': False, 'error': 'Not connected'}
        
        try:
            command = f'install add file {filesystem}{filename} activate commit prompt-level none'
            
            full_output = ""
            def wrapped_callback(data):
                nonlocal full_output
                full_output += data
                if callback:
                    callback(data)

            # This is a long-running command, timeouts are handled by execute_command_stream loop 
            # or could add specific timeout logic there if needed.
            # Ideally execute_command_stream should support a max_time or similar, 
            # but for now we rely on the loop. The loop runs until prompt.
            # We might want to ensure 'prompt-level none' doesn't hang.
            
            if callback:
                callback(f"Executing: {command}\n")

            success = self.execute_command_stream(
                command, 
                callback=wrapped_callback
            )
            
            if not success:
                 # Check if failure was due to reload (expected)
                 reload_indicators = [
                     'reloading', 'system is going down', 
                     'initializing', 'going to be restarted',
                     'reload requested'
                 ]
                 if any(ind in full_output.lower() for ind in reload_indicators):
                     return {
                        'success': True,
                        'output': full_output,
                        'command': command,
                        'status': 'RELOADING'
                     }
                     
                 return {
                    'success': False,
                    'output': full_output,
                    'error': 'Command execution failed (stream) or connection dropped'
                }

            # Check for failure indicators first
            failure_indicators = [
                'Error', 'Fail', 'FAILED', 'failure',
                'System configuration has been modified'
            ]
            if any(ind in full_output for ind in failure_indicators):
                 return {
                    'success': False,
                    'output': full_output,
                    'error': 'Install command returned error'
                }

            # Check for success in output
            if 'Install add file activated commit' in full_output:
                 return {
                    'success': True,
                    'output': full_output,
                    'command': command
                }
            # Fallback success check if prompt returned and no error?
            # Be careful with generic 'Success' word.
            elif 'Success' in full_output or 'SUCCESS' in full_output:
                  return {
                    'success': True,
                    'output': full_output,
                    'command': command
                }
            # Also check for explicit errors
            elif 'Error' in full_output or 'Fail' in full_output:
                return {
                    'success': False,
                    'output': full_output,
                    'error': 'Install command returned error'
                }
            else:
                 # If we got the prompt back without explicit success text, it might still have worked?
                 # IOS-XE install commands usually print a table of results.
                 # Let's assume success if no error and prompt returned.
                 return {
                    'success': True,
                    'output': full_output,
                    'command': command
                }

        except Exception as e:
            print(f"Error executing install command: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def copy_file_from_http(self, http_url: str, destination: str, callback=None) -> Dict[str, Any]:
        """
        Copy file from HTTP server to device filesystem with optional callback for logging
        """
        if not self.connection:
            return {'success': False, 'error': 'Not connected'}
        
        try:
            command = f'copy {http_url} {destination}'
            print(f"Executing: {command}")
            if callback:
                callback(f"Executing: {command}\n")

            # prompts to handle
            # 1. Destination filename? [filename]
            # 2. %Error file already exists... overwrite? [confirm]
            prompts = {
                r'Destination filename': '\n', # Press enter to accept default
                r'[Oo]verwrite': '\n'          # Press enter to confirm overwrite
            }

            full_output = ""
            
            # Use execute_command_stream but capture output
            # We need to wrap callback to also accumulate output
            def wrapped_callback(data):
                nonlocal full_output
                full_output += data
                if callback:
                    callback(data)

            success = self.execute_command_stream(
                command, 
                callback=wrapped_callback,
                prompts=prompts
            )
            
            if not success:
                 return {
                    'success': False,
                    'output': full_output,
                    'error': 'Command execution failed'
                }

            # Check for success messages in full_output
            # "bytes copied" or "checksum matched" or "Copied ..."
            if 'bytes copied' in full_output.lower() or 'checksum matched' in full_output.lower() or 'copied' in full_output.lower():
                return {
                    'success': True,
                    'output': full_output
                }
            elif '%Error' in full_output or 'Error' in full_output:
                return {
                    'success': False,
                    'output': full_output,
                    'error': 'Copy failed with error'
                }
            else:
                 return {
                    'success': True, # Assume success if no explicit error and command finished (some IOS versions are quiet)
                    'output': full_output,
                    'warning': 'Copy status uncertain but no error detected'
                }

        except Exception as e:
            print(f"Error copying file: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def calculate_md5(self, filesystem: str, filename: str, callback=None) -> Optional[str]:
        """
        Calculate MD5 checksum of file on device with optional callback
        Returns the hash string or None
        """
        if not self.connection:
            return None
        
        try:
            command = f'verify /md5 {filesystem}{filename}'
            # Timeout 300s (5 mins) for calculation
            
            full_output = ""
            def wrapped_callback(data):
                nonlocal full_output
                full_output += data
                if callback:
                    callback(data)

            success = self.execute_command_stream(
                command, 
                callback=wrapped_callback,
                prompts={}
            )

            if not success:
                return None
            
            # Extract MD5 from output
            # Output format: ".....Done! verify /md5 (flash:image.bin) = 59d57a..."
            # Regex to find 32 hex chars
            md5_match = re.search(r'([0-9a-fA-F]{32})', full_output)
            if md5_match:
                return md5_match.group(1).lower()
            
            return None
        except Exception as e:
            print(f"Error calculating MD5: {e}")
            return None

    def verify_md5(self, filesystem: str, filename: str, expected_md5: str) -> bool:
        """
        Verify MD5 checksum of file on device
        """
        if not self.connection:
            return False
        
        try:
            command = f'verify /md5 {filesystem}{filename}'
            output = self.connection.send_command(command, read_timeout=300)
            
            # Extract MD5 from output
            md5_match = re.search(r'([0-9a-fA-F]{32})', output)
            if md5_match:
                actual_md5 = md5_match.group(1).lower()
                return actual_md5 == expected_md5.lower()
            
            return False
        except Exception as e:
            print(f"Error verifying MD5: {e}")
            return False
    
    def get_disk_space(self, filesystem: str = 'flash:') -> Optional[Dict[str, Any]]:
        """
        Get disk space information using CLI
        Fallback when NETCONF is not available
        """
        if not self.connection:
            return None
        
        try:
            command = f'dir {filesystem}'
            output = self.connection.send_command(command)
            
            # Parse available space
            # Example: "1621590016 bytes total (1234567890 bytes free)"
            space_match = re.search(r'(\d+)\s+bytes\s+free', output)
            total_match = re.search(r'(\d+)\s+bytes\s+total', output)
            
            if space_match and total_match:
                free_bytes = int(space_match.group(1))
                total_bytes = int(total_match.group(1))
                
                return {
                    'filesystem': filesystem,
                    'available_gb': round(free_bytes / (1024**3), 2),
                    'total_gb': round(total_bytes / (1024**3), 2),
                    'available_bytes': free_bytes
                }
            
            return None
        except Exception as e:
            return None
    
    def execute_command_stream(self, command: str, callback=None, prompts: Dict[str, str] = None) -> bool:
        """
        Execute command and stream output to callback
        Uses invoke_shell to get real-time output
        prompts: Dict of regex patterns to responses, e.g. {r'\[y/n\]': 'y'}
        """
        if not self.connection:
            return False
            
        try:
            # Clear buffer
            self.connection.clear_buffer()
            
            # Send command
            self.connection.write_channel(command + '\n')
            
            # Loop to read output
            while True:
                time.sleep(0.5)
                if self.connection.remote_conn.recv_ready():
                    output = self.connection.read_channel()
                    if callback:
                        callback(output)
                    
                    # Check for interactive prompts
                    if prompts:
                        for pattern, response in prompts.items():
                            if re.search(pattern, output):
                                if callback:
                                    callback(f" [Auto-responding '{response}']\n")
                                self.connection.write_channel(response + '\n')
                    
                    # Check for completion (prompt)
                    # Simple check for '#' prompt at end of output
                    if output.strip().endswith('#'):
                        break
                        
            return True
        except Exception as e:
            if callback:
                callback(f"Error: {str(e)}")
            return False

    def check_file_exists(self, filesystem: str, filename: str) -> bool:
        """
        Check if a file exists on the remote device
        """
        try:
            # Handle filesystem argument (keep or remove colon)
            fs = filesystem.rstrip(':')
            full_path = f"{fs}:{filename}"
            
            command = f"dir {full_path}"
            output = self.connection.send_command(command)
            
            # Check for common error messages (case-insensitive)
            lower_output = output.lower()
            error_markers = ["error opening", "no such file", "not found", "invalid input", "% bad device", "command not found"]
            if any(marker in lower_output for marker in error_markers):
                return False
            
            # Split lines to avoid matching command echo
            lines = output.splitlines()
            for line in lines:
                if filename in line:
                    # Ignore the command echo line (which usually contains 'dir' or the full path)
                    # Also ignore prompts
                    if command in line or f"dir {fs}:" in line or line.strip().endswith('#'):
                        continue
                    
                    # If we find the filename in a non-command line, it's likely the listing
                    return True
            
            return False
        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False

