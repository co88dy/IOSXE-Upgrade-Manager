"""
NETCONF client for IOS-XE device communication
Uses ncclient for YANG model-based operations
"""

from ncclient import manager
from ncclient.operations import RPCError
import xmltodict
from typing import Dict, Any, Optional, List
import paramiko

# Global fix for legacy devices (TripleDES/SHA1 support)
paramiko.Transport._preferred_kex = (
    'diffie-hellman-group14-sha1',
    'diffie-hellman-group-exchange-sha1',
    'diffie-hellman-group1-sha1',
    'diffie-hellman-group-exchange-sha256',
    'ecdh-sha2-nistp256',
    'ecdh-sha2-nistp384',
    'ecdh-sha2-nistp521',
    'curve25519-sha256',
    'curve25519-sha256@libssh.org'
)
paramiko.Transport._preferred_ciphers = (
    'aes128-ctr',
    'aes192-ctr',
    'aes256-ctr',
    'aes128-cbc',
    'aes192-cbc',
    'aes256-cbc',
    '3des-cbc'
)
paramiko.Transport._preferred_keys = (
    'ssh-rsa',
    'rsa-sha2-256',
    'rsa-sha2-512',
    'ssh-dss',
    'ecdsa-sha2-nistp256',
    'ecdsa-sha2-nistp384',
    'ecdsa-sha2-nistp521',
    'ssh-ed25519'
)


class NetconfClient:
    """NETCONF operations for IOS-XE devices"""
    
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connection = None
    
    def connect(self) -> bool:
        """Establish NETCONF connection"""
        try:
            print(f"[DEBUG] Attempting NETCONF connection to {self.host}:{self.port} with username '{self.username}'")
            self.connection = manager.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                device_params={'name': 'iosxe'},
                hostkey_verify=False,
                look_for_keys=False,
                allow_agent=False,
                timeout=30
            )
            print(f"[DEBUG] NETCONF connection successful to {self.host}")
            return True
        except Exception as e:
            print(f"[ERROR] NETCONF connection failed to {self.host}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def disconnect(self):
        """Close NETCONF connection"""
        if self.connection:
            self.connection.close_session()
    
    def get_device_hardware(self) -> Optional[Dict[str, Any]]:
        """
        Get device hardware information using Cisco-IOS-XE-device-hardware-oper
        Returns hostname, serial, PID, and version
        """
        if not self.connection:
            return None
        
        try:
            # NETCONF filter for device hardware
            filter_xml = '''
            <filter>
                <device-hardware-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-device-hardware-oper">
                    <device-hardware>
                        <device-inventory/>
                    </device-hardware>
                </device-hardware-data>
            </filter>
            '''
            
            response = self.connection.get(filter_xml)
            data = xmltodict.parse(response.xml)
            
            # Parse the response
            hardware_data = data.get('rpc-reply', {}).get('data', {}).get('device-hardware-data', {})
            inventory = hardware_data.get('device-hardware', {}).get('device-inventory', [])
            
            # Extract chassis information
            if isinstance(inventory, dict):
                inventory = [inventory]
            
            chassis_info = None
            for item in inventory:
                if item.get('hw-type') == 'hw-type-chassis':
                    chassis_info = item
                    break
            
            if chassis_info:
                return {
                    'serial_number': chassis_info.get('serial-number', 'Unknown'),
                    'part_number': chassis_info.get('part-number', 'Unknown'),
                    'hw_description': chassis_info.get('hw-description', 'Unknown')
                }
            
            return None
        except Exception as e:
            print(f"Error getting device hardware: {e}")
            return None
    
    def get_system_info(self) -> Optional[Dict[str, Any]]:
        """
        Get system information (hostname, version)
        """
        if not self.connection:
            return None
        
        try:
            # Get hostname and version using native YANG models
            filter_xml = '''
            <filter>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <hostname/>
                    <version/>
                </native>
            </filter>
            '''
            
            response = self.connection.get_config(source='running', filter=filter_xml)
            data = xmltodict.parse(response.xml)
            
            native = data.get('rpc-reply', {}).get('data', {}).get('native', {})
            
            return {
                'hostname': native.get('hostname', 'Unknown'),
                'version': native.get('version', 'Unknown')
            }
        except Exception as e:
            print(f"Error getting system info: {e}")
            return None
    
    def get_filesystem_info(self, filesystem: str = 'flash:') -> Optional[Dict[str, Any]]:
        """
        Get filesystem information (available space)
        Uses Cisco-IOS-XE-platform-software-oper for disk space
        """
        if not self.connection:
            return None
        
        try:
            # Query filesystem data
            filter_xml = f'''
            <filter>
                <cisco-platform-software xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-platform-software-oper">
                    <q-filesystem>
                        <partitions>
                            <name>{filesystem}</name>
                        </partitions>
                    </q-filesystem>
                </cisco-platform-software>
            </filter>
            '''
            
            response = self.connection.get(filter_xml)
            data = xmltodict.parse(response.xml)
            
            partitions = data.get('rpc-reply', {}).get('data', {}).get('cisco-platform-software', {}).get('q-filesystem', {}).get('partitions', {})
            
            if partitions:
                available_bytes = int(partitions.get('available', 0))
                total_bytes = int(partitions.get('total-size', 0))
                
                return {
                    'filesystem': filesystem,
                    'available_gb': round(available_bytes / (1024**3), 2),
                    'total_gb': round(total_bytes / (1024**3), 2),
                    'available_bytes': available_bytes
                }
            
            return None
        except Exception as e:
            print(f"Error getting filesystem info: {e}")
            return None
    
    def get_stack_members(self) -> List[Dict[str, Any]]:
        """
        Get stack member information for switches
        Returns list of stack members with their filesystems
        """
        if not self.connection:
            return []
        
        try:
            filter_xml = '''
            <filter>
                <stack xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
                    <switch/>
                </stack>
            </filter>
            '''
            
            response = self.connection.get(filter_xml)
            data = xmltodict.parse(response.xml)
            
            stack_data = data.get('rpc-reply', {}).get('data', {}).get('stack', {}).get('switch', [])
            
            if isinstance(stack_data, dict):
                stack_data = [stack_data]
            
            members = []
            for member in stack_data:
                member_num = member.get('switch-number', '1')
                members.append({
                    'member_number': member_num,
                    'filesystem': f'flash-{member_num}:',
                    'state': member.get('state', 'Unknown')
                })
            
            return members
        except Exception as e:
            print(f"Error getting stack members: {e}")
            return []
    
    def get_boot_variables(self) -> Optional[Dict[str, Any]]:
        """
        Get boot system configuration
        """
        if not self.connection:
            return None
        
        try:
            filter_xml = '''
            <filter>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <boot>
                        <system/>
                    </boot>
                </native>
            </filter>
            '''
            
            response = self.connection.get_config(source='running', filter=filter_xml)
            data = xmltodict.parse(response.xml)
            
            boot_data = data.get('rpc-reply', {}).get('data', {}).get('native', {}).get('boot', {})
            
            return {
                'boot_system': boot_data.get('system', 'Not configured')
            }
        except Exception as e:
            print(f"Error getting boot variables: {e}")
            return None
    
    def determine_device_role(self, part_number: str) -> str:
        """
        Determine if device is a Switch or Router based on PID
        """
        part_number = part_number.upper()
        
        # Switch patterns
        if any(pattern in part_number for pattern in ['C9', 'C3850', 'C3650']):
            return 'Switch'
        
        # Router patterns
        if any(pattern in part_number for pattern in ['ASR', 'ISR', 'C8']):
            return 'Router'
        
        return 'Unknown'
    
    def get_filesystem_for_role(self, device_role: str) -> str:
        """
        Get appropriate filesystem based on device role
        """
        if device_role == 'Switch':
            return 'flash:'
        elif device_role == 'Router':
            return 'bootflash:'
        else:
            return 'flash:'
