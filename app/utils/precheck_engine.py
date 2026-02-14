"""
Pre-check engine for IOS-XE upgrade validation
Implements all required pre-flight checks before upgrade
"""

from typing import Dict, Any, List
from app.utils.netconf_client import NetconfClient
from app.utils.ssh_client import SSHClient


class PreCheckEngine:
    """Pre-check validation engine"""
    
    def __init__(self, ip_address: str, username: str, password: str, netconf_port: int = 830, enable_password: str = ""):
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.netconf_port = netconf_port
        self.results = []
    
    def run_all_checks(self, current_version: str, target_version: str, 
                       device_role: str, filesystem: str, target_image_filename: str = "", target_image_size_mb: float = 0) -> List[Dict[str, Any]]:
        """
        Run all pre-checks and return results
        """
        self.results = []
        
        # Check 1: Version Comparison
        self._check_version_difference(current_version, target_version)
        
        # Check 2: Boot Variable Integrity
        self._check_boot_variables(device_role)
        
        # Check 3: Disk Space Thresholds
        self._check_disk_space(device_role, filesystem, target_image_size_mb)
        
        # Check 4: ROMMON Flag Validation
        self._check_rommon_flags()

        # Check 5: NPE Image Detection
        if target_image_filename:
            self._check_npe_image(target_image_filename)

        # Check 6: Image Presence Verification
        if target_image_filename:
            self._check_image_presence(filesystem, target_image_filename)

        # Check 7: Commit Status Check
        self._check_commit_status()
        
        return self.results

    def _check_image_presence(self, filesystem: str, target_image_filename: str):
        """Check if target image exists on the device"""
        try:
            ssh = SSHClient(self.ip_address, self.username, self.password, self.enable_password)
            if ssh.connect():
                exists = ssh.check_file_exists(filesystem, target_image_filename)
                ssh.disconnect()
                
                if exists:
                    self.results.append({
                        'check_name': 'Image Presence',
                        'result': 'PASS',
                        'message': f'Verified: {target_image_filename} exists on {filesystem}:'
                    })
                else:
                    self.results.append({
                        'check_name': 'Image Presence',
                        'result': 'FAIL',
                        'message': f'Image {target_image_filename} NOT FOUND on {filesystem}:. Please copy the image first.'
                    })
            else:
                self.results.append({
                    'check_name': 'Image Presence',
                    'result': 'ERROR',
                    'message': 'Could not connect via SSH to verify image presence'
                })
        except Exception as e:
            self.results.append({
                'check_name': 'Image Presence',
                'result': 'ERROR',
                'message': f'Error checking image presence: {str(e)}'
            })
    
    def _parse_version(self, version_str: str) -> List[int]:
        """
        Parse version string into a list of integers for comparison
        Handles strings like '17.03.02', '17.3.2', '16.12.5', '16.12.05a'
        Removes non-numeric suffixes/prefixes
        """
        import re
        try:
            # Clean string: remove common prefixes/suffixes if present (though usually passed clean)
            # Remove .SPA, .bin, etc
            clean_ver = re.sub(r'(?i)\.(bin|spa|pkg)$', '', version_str)
            
            # Find the main version pattern (digits.digits.digits...)
            # We look for the first sequence of numbers separated by dots
            match = re.search(r'(\d+(?:\.\d+)+)', clean_ver)
            if match:
                version_part = match.group(1)
                return [int(v) for v in version_part.split('.')]
            
            return []
        except Exception:
            return []

    def _check_version_difference(self, current_version: str, target_version: str):
        """Check if target version is different from current version and detect downgrades"""
        
        # Parse versions
        curr_ver = self._parse_version(current_version)
        tgt_ver = self._parse_version(target_version)
        
        # Fallback to string comparison if parsing fails
        if not curr_ver or not tgt_ver:
            if current_version == target_version:
                self.results.append({
                    'check_name': 'Version Comparison',
                    'result': 'FAIL',
                    'message': f'Target version ({target_version}) is the same as current version ({current_version})'
                })
            else:
                self.results.append({
                    'check_name': 'Version Comparison',
                    'result': 'PASS',
                    'message': f'Target version ({target_version}) differs from current version ({current_version})'
                })
            return

        # Compare versions
        if curr_ver == tgt_ver:
             self.results.append({
                'check_name': 'Version Comparison',
                'result': 'FAIL',
                'message': f'Target version ({target_version}) is the same as current version ({current_version})'
            })
        elif tgt_ver < curr_ver:
            # Downgrade detected
            self.results.append({
                'check_name': 'Version Comparison',
                'result': 'WARN',
                'message': f'Target version ({target_version}) is lower than current version ({current_version}). This will cause a downgrade. Please confirm downgrade compatibility.'
            })
        else:
            # Upgrade (tgt > curr)
            self.results.append({
                'check_name': 'Version Comparison',
                'result': 'PASS',
                'message': f'Target version ({target_version}) is higher than current version ({current_version}). Upgrade path looks valid.'
            })
    
    def _check_boot_variables(self, device_role: str):
        """Check boot system configuration for Install Mode"""
        boot_info = None
        
        # Try NETCONF first
        try:
            netconf = NetconfClient(self.ip_address, self.netconf_port, self.username, self.password)
            if netconf.connect():
                boot_info = netconf.get_boot_variables()
                netconf.disconnect()
        except Exception as e:
            print(f"NETCONF boot check failed: {e}")

        # Check if NETCONF retrieved valid data
        if boot_info:
            boot_system = boot_info.get('boot_system', '')
            
            # For Install Mode, boot should point to packages.conf
            if 'packages.conf' in str(boot_system):
                self.results.append({
                    'check_name': 'Boot Variable Integrity',
                    'result': 'PASS',
                    'message': 'Boot system correctly points to packages.conf (Install Mode)'
                })
            else:
                self.results.append({
                    'check_name': 'Boot Variable Integrity',
                    'result': 'WARN',
                    'message': f'Boot system: {boot_system}. Verify Install Mode configuration.'
                })
        else:
            # Fallback to SSH
            try:
                ssh = SSHClient(self.ip_address, self.username, self.password, self.enable_password)
                if ssh.connect():
                    boot_var = ssh.get_boot_variables()
                    ssh.disconnect()
                    
                    if boot_var:
                        if 'packages.conf' in str(boot_var):
                            self.results.append({
                                'check_name': 'Boot Variable Integrity',
                                'result': 'PASS',
                                'message': 'Boot system correctly points to packages.conf (Install Mode) [via SSH]'
                            })
                        else:
                            self.results.append({
                                'check_name': 'Boot Variable Integrity',
                                'result': 'WARN',
                                'message': f'Boot system: {boot_var}. Verify Install Mode configuration. [via SSH]'
                            })
                    else:
                        self.results.append({
                            'check_name': 'Boot Variable Integrity',
                            'result': 'WARN',
                            'message': 'Could not retrieve boot variables via NETCONF or SSH'
                        })
                else:
                    self.results.append({
                        'check_name': 'Boot Variable Integrity',
                        'result': 'WARN',
                        'message': 'NETCONF and SSH unavailable for boot check'
                    })
            except Exception as e:
                self.results.append({
                    'check_name': 'Boot Variable Integrity',
                    'result': 'ERROR',
                    'message': f'Error checking boot variables: {str(e)}'
                })
    
    def _check_disk_space(self, device_role: str, filesystem: str, target_image_size_mb: float = 0):
        """Check disk space thresholds"""
        fs_info_list = []
        netconf_success = False

        # Try NETCONF first
        try:
            netconf = NetconfClient(self.ip_address, self.netconf_port, self.username, self.password)
            
            if netconf.connect():
                # For switches, check all stack members
                if device_role == 'Switch':
                    stack_members = netconf.get_stack_members()
                    
                    if stack_members:
                        for member in stack_members:
                            fs_info = netconf.get_filesystem_info(member['filesystem'])
                            if fs_info:
                                fs_info_list.append(fs_info)
                        if fs_info_list:
                             netconf_success = True
                    else:
                        # Single switch, check main filesystem
                        fs_info = netconf.get_filesystem_info(filesystem)
                        if fs_info:
                            fs_info_list.append(fs_info)
                            netconf_success = True
                else:
                    # Router - check single filesystem
                    fs_info = netconf.get_filesystem_info(filesystem)
                    if fs_info:
                        fs_info_list.append(fs_info)
                        netconf_success = True
                
                netconf.disconnect()
        except Exception as e:
             print(f"NETCONF disk check failed: {e}")

        # Evaluate NETCONF results
        if netconf_success and fs_info_list:
            all_pass = True
            messages = []
            for fs_info in fs_info_list:
                 available_gb = fs_info['available_gb']
                 # For stack members, we might want member number, but simple FS name is ok
                 fs_name = fs_info['filesystem']
                 
                 if available_gb < 1:
                    all_pass = False
                    messages.append(f"{fs_name}: {available_gb}GB (ERROR: <1GB)")
                 elif available_gb < 2:
                    messages.append(f"{fs_name}: {available_gb}GB (WARNING: <2GB)")
                 else:
                    messages.append(f"{fs_name}: {available_gb}GB (OK)")
            
            # Consolidate results
            if not all_pass:
                 self.results.append({
                    'check_name': 'Disk Space Thresholds',
                    'result': 'FAIL',
                    'message': '; '.join(messages)
                })
            elif any('WARNING' in msg for msg in messages):
                self.results.append({
                    'check_name': 'Disk Space Thresholds',
                    'result': 'WARN',
                    'message': '; '.join(messages)
                })
            else:
                 self.results.append({
                    'check_name': 'Disk Space Thresholds',
                    'result': 'PASS',
                    'message': '; '.join(messages)
                })
            return

        # Fallback to SSH if NETCONF failed or returned no data
        try:
            ssh = SSHClient(self.ip_address, self.username, self.password, self.enable_password)
            if ssh.connect():
                # Note: SSH implementation in ssh_client currently only gets main filesystem
                # Improvements to get stack members via SSH could be added later
                fs_info = ssh.get_disk_space(filesystem)
                ssh.disconnect()
                
                if fs_info:
                    self._evaluate_disk_space(fs_info, target_image_size_mb)
                else:
                     self.results.append({
                        'check_name': 'Disk Space Thresholds',
                        'result': 'ERROR',
                        'message': 'Could not retrieve filesystem information via SSH'
                    })
            else:
                 self.results.append({
                    'check_name': 'Disk Space Thresholds',
                    'result': 'ERROR',
                    'message': 'Could not connect via SSH to check disk space'
                })
        except Exception as e:
            self.results.append({
                'check_name': 'Disk Space Thresholds',
                'result': 'ERROR',
                'message': f'Error checking disk space: {str(e)}'
            })
    
    def _evaluate_disk_space(self, fs_info: Dict[str, Any], target_image_size_mb: float = 0):
        """Evaluate disk space and add result"""
        if fs_info:
            available_gb = fs_info['available_gb']
            # fs_info usually returns available_gb which is float.
            # target_image_size_mb is in MB.
            # We need to compare available_gb * 1024 to target_image_size_mb * 2
            
            available_mb = available_gb * 1024
            required_mb = target_image_size_mb * 2
            
            # If target_image_size_mb is 0 (e.g. unknown local file), fallback to old checks or just warn?
            # User specifically asked to remove old constraints.
            # But we must have a safe fallback if we don't know the image size used to happen with remote files?
            # Repo model ensures local file exists so size should be known.
            
            if target_image_size_mb > 0:
                if available_mb < required_mb:
                     self.results.append({
                        'check_name': 'Disk Space Thresholds',
                        'result': 'FAIL',
                        'message': f'{fs_info["filesystem"]} has {available_gb}GB available. Required: {required_mb/1024:.2f}GB (2x image size)'
                    })
                else:
                    self.results.append({
                        'check_name': 'Disk Space Thresholds',
                        'result': 'PASS',
                        'message': f'{fs_info["filesystem"]} has {available_gb}GB available (Sufficient: > {required_mb/1024:.2f}GB)'
                    })
            else:
                # Fallback if image size unknown - maybe just use a safe default like 2GB? 
                # Or user said remove old constraints, maybe that means ONLY rely on image size?
                # If we don't know image size, we can't do the check they asked for.
                # Let's fallback to a warning.
                if available_gb < 1:
                     self.results.append({
                        'check_name': 'Disk Space Thresholds',
                        'result': 'WARN',
                        'message': f'{fs_info["filesystem"]} has {available_gb}GB available. Could not verify against image size.'
                    })
                else:
                    self.results.append({
                        'check_name': 'Disk Space Thresholds',
                        'result': 'PASS',
                        'message': f'{fs_info["filesystem"]} has {available_gb}GB available (Image size unknown)'
                    })
        else:
            self.results.append({
                'check_name': 'Disk Space Thresholds',
                'result': 'ERROR',
                'message': 'Could not retrieve filesystem information'
            })
    
    def _check_rommon_flags(self):
        """Check ROMMON variables for SWITCH_IGNORE_STARTUP_CFG flag"""
        try:
            ssh = SSHClient(self.ip_address, self.username, self.password, self.enable_password)
            if ssh.connect():
                rommon_info = ssh.check_rommon_variables()
                ssh.disconnect()
                
                if 'error' in rommon_info:
                    self.results.append({
                        'check_name': 'ROMMON Flag Validation',
                        'result': 'ERROR',
                        'message': f'Error checking ROMMON: {rommon_info["error"]}'
                    })
                elif rommon_info.get('ignore_startup_cfg'):
                    self.results.append({
                        'check_name': 'ROMMON Flag Validation',
                        'result': 'FAIL',
                        'message': 'CRITICAL: SWITCH_IGNORE_STARTUP_CFG=1 detected. Device will ignore startup config on reboot!'
                    })
                else:
                    self.results.append({
                        'check_name': 'ROMMON Flag Validation',
                        'result': 'PASS',
                        'message': 'ROMMON variables OK (no ignore startup config flag)'
                    })
            else:
                self.results.append({
                    'check_name': 'ROMMON Flag Validation',
                    'result': 'ERROR',
                    'message': 'Could not connect via SSH to check ROMMON variables'
                })
        except Exception as e:
            self.results.append({
                'check_name': 'ROMMON Flag Validation',
                'result': 'ERROR',
                'message': f'Error checking ROMMON flags: {str(e)}'
            })
    
    def all_checks_passed(self) -> bool:
        """Check if all pre-checks passed (no FAIL or ERROR results)"""
        for result in self.results:
            if result['result'] in ['FAIL', 'ERROR']:
                return False
        return True

    def _check_npe_image(self, target_image_filename: str):
        """Check if target image is NPE (No Payload Encryption)"""
        if 'npe' in target_image_filename.lower():
            self.results.append({
                'check_name': 'NPE Image Detection',
                'result': 'WARN',
                'message': f'Target image ({target_image_filename}) is an NPE (No Payload Encryption) image. Some features may be unavailable.'
            })
        else:
            self.results.append({
                'check_name': 'NPE Image Detection',
                'result': 'PASS',
                'message': 'Target image supports full encryption features (Non-NPE)'
            })

    def _check_commit_status(self):
        """Check if current software is committed"""
        try:
            # Method 1: NETCONF (TBD - keeping SSH as primary for now as it's more reliable for this specific output)
            
            # Method 2: SSH
            ssh = SSHClient(self.ip_address, self.username, self.password, self.enable_password)
            if ssh.connect():
                output = ssh.get_install_summary()
                ssh.disconnect()
                
                if not output:
                    self.results.append({
                        'check_name': 'Commit Status Check',
                        'result': 'WARN',
                        'message': 'Could not retrieve install summary via SSH'
                    })
                    return
                
                # Parse output to find committed package
                # Look for line with 'IMG' and 'C' state
                committed_found = False
                active_uncommitted = False
                
                for line in output.splitlines():
                    # Typical output line: " IMG   C    17.09.04.0.290476"
                    if 'IMG' in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            state = parts[1]
                            if 'C' in state:
                                committed_found = True
                            elif 'U' in state: # Activated & Uncommitted
                                active_uncommitted = True
                
                if active_uncommitted:
                    self.results.append({
                        'check_name': 'Commit Status Check',
                        'result': 'WARN',
                        'message': '⚠️ Current image is ACTIVATED but NOT COMMITTED. An auto-abort timer may be running.'
                    })
                elif committed_found:
                    self.results.append({
                        'check_name': 'Commit Status Check',
                        'result': 'PASS',
                        'message': '✅ Current image is committed'
                    })
                else:
                    # Could be legacy bundle mode or parsing failed
                    # Check if Bundle Mode was detected earlier (Check 2) to avoid double warning
                    is_bundle = False
                    for res in self.results:
                        if res['check_name'] == 'Boot Variable Integrity' and 'packages.conf' not in res['message'] and 'WARN' in res['result']:
                             # Likely bundle mode, so install summary might be empty or different
                             is_bundle = True
                    
                    if is_bundle:
                        self.results.append({
                            'check_name': 'Commit Status Check',
                            'result': 'PASS', # Not applicable for bundle mode efficiently
                            'message': 'Skipped (Device appears to be in Bundle Mode)'
                        })
                    else:
                        self.results.append({
                            'check_name': 'Commit Status Check',
                            'result': 'WARN',
                            'message': 'Could not verify commit status. Output may vary or install mode not active.'
                        })

            else:
                 self.results.append({
                    'check_name': 'Commit Status Check',
                    'result': 'WARN',
                    'message': 'Could not connect via SSH to verify commit status'
                })

        except Exception as e:
            self.results.append({
                'check_name': 'Commit Status Check',
                'result': 'ERROR',
                'message': f'Error checking commit status: {str(e)}'
            })
