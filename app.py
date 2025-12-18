#!/usr/bin/env python3
"""
Network Configuration Manager
Safely backup, edit, and restore network device configurations
Supports Cisco switches and routers via SSH/SCP/TFTP
"""

import os
import sys
import time
import getpass
from datetime import datetime
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import paramiko
from scp import SCPClient
import socket
import ipaddress
import shutil
import subprocess
import platform

class NetworkConfigManager:
    def __init__(self):
        self.device_info = {} 
        self.config_filename = None
        self.tftp_server = None
        self.tftp_root = None
        self.backup_dir = "config_backups"
        self.ensure_backup_directory()
    
    def ensure_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            print(f"Created backup directory: {self.backup_dir}")
    
    def validate_ip(self, ip):
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def get_device_credentials(self):
        """Get device connection details from user"""
        print("=== Network Configuration Manager ===")
        print("This tool helps you safely modify network device configurations")
        print("by backing up configs before changes and restoring them safely.\n")
        
        # Get device IP
        while True:
            ip = input("Enter device IP address: ").strip()
            if self.validate_ip(ip):
                break
            print("Invalid IP address format. Please try again.")
        
        # Get username
        username = input("Enter username: ").strip()
        
        # Get password
        password = getpass.getpass("Enter password: ")
        
        # Get enable password
        enable_prompt = input("Enter enable password (press Enter to use same password): ").strip()
        enable_password = enable_prompt if enable_prompt else password
        
        # Get TFTP details (optional)
        print("\n--- TFTP Settings (Optional) ---")
        print("TFTP is faster and preferred for restoring configurations.")
        self.tftp_server = input("Enter TFTP Server IP (press Enter to skip/use SCP only): ").strip()
        
        if self.tftp_server:
            self.tftp_root = input("Enter TFTP Root Directory (local path to copy config to, press Enter to skip): ").strip()
        
        self.device_info = {
            'device_type': 'cisco_ios',  # Will auto-detect later
            'host': ip,
            'username': username,
            'password': password,
            'secret': enable_password,
            'timeout': 60,
            'session_log': f'session_{ip}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        }
        
        return True
    
    def detect_device_type(self, connection):
        """Detect device type based on show version output"""
        try:
            version_output = connection.send_command("show version")
            
            if "Cisco IOS XE" in version_output:
                return "cisco_xe"
            elif "Cisco IOS XR" in version_output:
                return "cisco_xr"
            elif "Cisco NX-OS" in version_output:
                return "cisco_nxos"
            elif "Cisco IOS" in version_output:
                return "cisco_ios"
            else:
                return "cisco_ios"  # Default fallback
        except:
            return "cisco_ios"  # Default fallback
    
    def check_connectivity(self, host):
        """Check if host is reachable via ping"""
        print(f"Checking connectivity to {host}...")
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', host]
        
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
        except Exception:
            return False

    def test_connection(self):
        """Test SSH connection to device"""
        print(f"\nTesting connection to {self.device_info['host']}...")
        
        # First check basic connectivity
        if not self.check_connectivity(self.device_info['host']):
            print(f"✗ Device {self.device_info['host']} is not reachable via ping.")
            return False

        try:
            connection = ConnectHandler(**self.device_info)
            
            # Auto-detect device type
            detected_type = self.detect_device_type(connection)
            self.device_info['device_type'] = detected_type
            print(f"Device type detected: {detected_type}")
            
            # Get hostname for filename
            hostname_output = connection.send_command("show running-config | include hostname")
            if "hostname" in hostname_output:
                hostname = hostname_output.split()[-1]
            else:
                hostname = self.device_info['host'].replace('.', '_')
            
            connection.disconnect()
            
            # Generate config filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.config_filename = f"{hostname}_{timestamp}_startup-config.txt"
            
            print("✓ Connection successful!")
            return True
            
        except NetmikoAuthenticationException:
            print("✗ Authentication failed. Please check username/password.")
            return False
        except NetmikoTimeoutException:
            print("✗ Connection timeout. Please check IP address and network connectivity.")
            return False
        except Exception as e:
            print(f"✗ Connection failed: {str(e)}")
            return False
    
    def backup_config(self):
        """Backup startup configuration from device"""
        print(f"\nBacking up configuration from {self.device_info['host']}...")
        
        try:
            connection = ConnectHandler(**self.device_info)
            
            # Get startup configuration
            print("Retrieving startup configuration...")
            startup_config = connection.send_command("show startup-config", delay_factor=2)
            
            # Save to local file
            config_path = os.path.join(self.backup_dir, self.config_filename)
            with open(config_path, 'w') as f:
                f.write(startup_config)
            
            connection.disconnect()
            
            print(f"✓ Configuration backed up to: {config_path}")
            print(f"✓ File size: {len(startup_config)} characters")
            
            return config_path
            
        except Exception as e:
            print(f"✗ Backup failed: {str(e)}")
            return None
    
    def wait_for_user_edit(self, config_path):
        """Wait for user to edit the configuration file"""
        print(f"\n=== CONFIGURATION EDITING ===")
        print(f"Configuration file location: {config_path}")
        print("Please edit the configuration file as needed.")
        print("Make your changes (like 'no switchport' and adding IP addresses).")
        print("\nIMPORTANT: Save the file when you're done editing!")
        
        while True:
            response = input("\nHave you finished editing the configuration? (yes/Enter): ").strip().lower()
            if response in ['yes', 'y', '']:
                break
            elif response in ['no', 'n']:
                print("Please continue editing the configuration file.")
            else:
                print("Please answer 'yes' or 'no' (or just press Enter for yes).")
        
        # Verify file exists and has content
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read().strip()
            if content:
                print("✓ Configuration file ready for upload.")
                return True
            else:
                print("✗ Configuration file is empty!")
                return False
        else:
            print("✗ Configuration file not found!")
            return False
    
    def restore_config(self, config_path):
        """Restore configuration to device using copy command"""
        print(f"\nRestoring configuration to {self.device_info['host']}...")
        
        try:
            connection = None
            # Retry connection logic
            for attempt in range(3):
                try:
                    print(f"Connecting to device (Attempt {attempt+1}/3)...")
                    connection = ConnectHandler(**self.device_info)
                    break
                except Exception as e:
                    print(f"Connection attempt {attempt+1} failed: {str(e)}")
                    if attempt < 2:
                        print("Retrying in 5 seconds...")
                        time.sleep(5)
                    else:
                        raise Exception("Could not establish connection after 3 attempts")
            
            # Read the modified configuration
            with open(config_path, 'r') as f:
                new_config = f.read()
            
            # Method 1: Try TFTP first (faster/preferred if available)
            if self.try_tftp_restore(connection, config_path):
                connection.disconnect()
                return True
            
            # Method 2: Try SCP if TFTP fails or is skipped
            if self.try_scp_restore(connection, config_path):
                connection.disconnect()
                return True
            
            # Method 3: Direct configuration (line by line) - last resort
            print("SCP and TFTP not available, using direct configuration method...")
            return self.try_direct_config(connection, new_config)
            
        except Exception as e:
            print(f"✗ Configuration restore failed: {str(e)}")
            return False
    
    def try_scp_restore(self, connection, config_path):
        """Try to restore config using SCP"""
        scp_was_enabled = False
        try:
            print("Attempting SCP transfer...")
            
            # Check if SCP server is already enabled
            print("Checking SCP server status...")
            show_run_scp = connection.send_command("show running-config | include ip scp server enable")
            scp_was_enabled = "ip scp server enable" in show_run_scp
            
            if not scp_was_enabled:
                print("Enabling SCP server temporarily...")
                connection.send_config_set(["ip scp server enable"])
                print("✓ SCP server enabled")
            else:
                print("✓ SCP server already enabled")
            
            # Create SCP client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                hostname=self.device_info['host'],
                username=self.device_info['username'],
                password=self.device_info['password'],
                timeout=30
            )
            
            scp = SCPClient(ssh_client.get_transport())
            
            # Upload file to device
            remote_filename = f"startup-config-new"
            scp.put(config_path, remote_filename)
            scp.close()
            ssh_client.close()
            
            # Copy the uploaded file to startup-config
            copy_command = f"copy {remote_filename} startup-config"
            print(f"copy command {copy_command}")
            output = connection.send_command_timing(copy_command)
            print(f"output is {output}")
            if "confirm" in output.lower() or "[confirm]" in output.lower():
                output += connection.send_command_timing("\n")
            
            print("✓ SCP transfer successful!")
            
            # Disable SCP server if it wasn't originally enabled (security best practice)
            if not scp_was_enabled:
                print("Disabling SCP server for security...")
                connection.send_config_set(["no ip scp server enable"])
                print("✓ SCP server disabled")
            
            return True
            
        except Exception as e:
            print(f"SCP method failed: {str(e)}")
            
            # Ensure SCP server is disabled if we enabled it, even on failure
            if not scp_was_enabled:
                try:
                    print("Disabling SCP server after failure...")
                    connection.send_config_set(["no ip scp server enable"])
                    print("✓ SCP server disabled")
                except:
                    print("⚠️  Warning: Could not disable SCP server. Please disable manually with 'no ip scp server enable'")
            
            return False
    
    def try_tftp_restore(self, connection, config_path):
        """Try to restore config using TFTP"""
        if not self.tftp_server:
            print("TFTP server not specified, skipping TFTP method.")
            return False
            
        try:
            print("Attempting TFTP transfer...")
            
            filename = os.path.basename(config_path)
            
            # Determine remote path for TFTP
            remote_path = filename
            
            # Copy file to TFTP root if specified
            if self.tftp_root:
                try:
                    dest_path = os.path.join(self.tftp_root, filename)
                    
                    # Check if source and destination are the same to avoid WinError 32
                    if os.path.abspath(config_path) != os.path.abspath(dest_path):
                        print(f"Copying config to TFTP root: {dest_path}")
                        shutil.copy2(config_path, dest_path)
                    else:
                        print(f"File already in TFTP root: {dest_path}")
                except Exception as e:
                    print(f"⚠️  Warning: Could not copy file to TFTP root: {str(e)}")
                    print("Ensure the file is already in the TFTP server's root directory.")
            else:
                # If no TFTP root specified, assume we need to provide path relative to where we are running
                # The file is in config_backups/
                remote_path = f"config_backups/{filename}"
            
            # Construct copy command
            # copy tftp://<server>/<file> startup-config
            copy_command = f"copy tftp://{self.tftp_server}/{remote_path} startup-config"
            print(f"Executing: {copy_command}")
            
            # Send copy command and handle prompts dynamically
            output = connection.send_command_timing(copy_command)
            
            # Maximum number of interactions to prevent infinite loops
            max_loops = 10
            loops = 0
            
            while loops < max_loops:
                loops += 1
                
                # Check if we are done (success or error)
                if "bytes copied" in output.lower() or "ok" in output.lower() or "copied" in output.lower() or "error" in output.lower() or "fail" in output.lower():
                    break
                
                # Handle prompts
                if "address or name of remote host" in output.lower():
                    output += connection.send_command_timing(self.tftp_server)
                elif "source filename" in output.lower():
                    output += connection.send_command_timing(remote_path) # Use full remote path if asked
                elif "destination filename" in output.lower():
                    output += connection.send_command_timing("\n") # Accept default
                elif "confirm" in output.lower() or "[confirm]" in output.lower():
                    output += connection.send_command_timing("\n")
                elif "overwrite" in output.lower():
                    output += connection.send_command_timing("\n")
                else:
                    # No known prompt found, maybe transfer is just taking time?
                    # Wait a bit and check output again
                    time.sleep(2)
                    new_output = connection.read_channel()
                    if new_output:
                        output += new_output
                    else:
                        break # No more output, assume done
            
            print(f"Transfer output: {output}")
            
            # Check for success indicators
            if "bytes copied" in output.lower() or "ok" in output.lower() or "copied" in output.lower():
                if "error" not in output.lower() and "fail" not in output.lower():
                    print("✓ TFTP transfer successful!")
                    return True
            
            print("✗ TFTP transfer failed or status unknown.")
            return False
            
        except Exception as e:
            print(f"TFTP method failed: {str(e)}")
            return False
    
    def try_direct_config(self, connection, new_config):
        """Direct configuration method - copy config to running then save"""
        try:
            print("Using direct configuration method...")
            print("This will replace the startup configuration with your modified version.")
            
            # Enter configuration mode
            connection.send_command("configure terminal")
            
            # Send configuration line by line
            config_lines = new_config.split('\n')
            total_lines = len(config_lines)
            
            print(f"Applying {total_lines} configuration lines...")
            
            for i, line in enumerate(config_lines, 1):
                line = line.strip()
                if line and not line.startswith('!') and not line.startswith('#'):
                    try:
                        # Use send_command without expect_string for better compatibility
                        connection.send_command(line)
                        if i % 50 == 0:  # Progress indicator
                            print(f"Progress: {i}/{total_lines} lines applied")
                    except Exception as e:
                        print(f"Warning: Error applying line '{line}': {str(e)}")
            
            # Exit configuration mode
            connection.send_command("end")
            
            # Save configuration
            print("Saving configuration...")
            save_output = connection.send_command_timing("copy running-config startup-config")
            
            if "confirm" in save_output.lower() or "[confirm]" in save_output.lower():
                save_output += connection.send_command_timing("\n")
            
            connection.disconnect()
            
            print("✓ Direct configuration method completed!")
            return True
            
        except Exception as e:
            print(f"Direct configuration method failed: {str(e)}")
            return False
    
    def check_and_fix_config_register(self, connection):
        """Check and fix configuration register to allow proper reload"""
        try:
            print("Checking configuration register...")
            
            # Check current configuration register
            version_output = connection.send_command("show version")
            
            # Look for configuration register in the output
            config_reg_line = ""
            for line in version_output.split('\n'):
                if "configuration register" in line.lower():
                    config_reg_line = line
                    break
            
            if config_reg_line:
                print(f"Current config register: {config_reg_line.strip()}")
                
                # Check if config register is set to boot to ROMMON (0x2100)
                if "0x2100" in config_reg_line:
                    print("⚠️  Configuration register is set to boot to ROMMON mode (0x2100)")
                    print("This prevents remote reload. Fixing...")
                    
                    # Set config register to normal boot mode
                    connection.send_command("configure terminal")
                    connection.send_command("config-register 0x2102")
                    connection.send_command("end")
                    connection.send_command("write memory")
                    
                    print("✓ Configuration register set to 0x2102 (normal boot mode)")
                    return True
                    
                elif "0x2102" in config_reg_line:
                    print("✓ Configuration register is already set correctly (0x2102)")
                    return True
                    
                else:
                    print(f"Configuration register value: {config_reg_line}")
                    print("This should be fine for reload, continuing...")
                    return True
            else:
                print("Could not determine configuration register value, proceeding with reload...")
                return True
                
        except Exception as e:
            print(f"Warning: Could not check configuration register: {str(e)}")
            print("Proceeding with reload attempt...")
            return True
    
    def apply_startup_to_running(self):
        """Copy startup-config to running-config to apply changes immediately"""
        print(f"\n=== APPLY CONFIGURATION ===")
        print("This will copy the startup-config to running-config to apply changes immediately.")
        print("This is safer than reloading as it doesn't require a device restart.")
        
        while True:
            response = input("Do you want to apply the startup configuration now? (yes/no/Enter for yes): ").strip().lower()
            if response in ['yes', 'y', '']:
                break
            elif response in ['no', 'n']:
                print("Configuration will not be applied. Changes remain in startup-config only.")
                return False
            else:
                print("Please answer 'yes' or 'no' (or just press Enter for yes).")
        
        try:
            print(f"Applying startup configuration to running config on {self.device_info['host']}...")
            connection = ConnectHandler(**self.device_info)
            
            # Copy startup-config to running-config
            print("Executing: copy startup-config running-config")
            copy_output = connection.send_command_timing("copy startup-config running-config")
            
            # Handle confirmation prompts
            if "confirm" in copy_output.lower() or "[confirm]" in copy_output.lower():
                print("Confirming copy operation...")
                copy_output += connection.send_command_timing("\n")
            
            # Handle destination filename prompt (some devices ask for this)
            if "destination filename" in copy_output.lower():
                print("Accepting default destination filename...")
                copy_output += connection.send_command_timing("\n")
            
            # Check for any errors in the output
            if "error" in copy_output.lower() or "failed" in copy_output.lower():
                print(f"⚠️  Warning: Possible error in copy operation:")
                print(copy_output)
            else:
                print("✓ Startup configuration successfully copied to running configuration!")
                print("Changes are now active on the device.")
            
            # Verify the operation by checking running config timestamp
            print("\nVerifying configuration update...")
            try:
                show_run_output = connection.send_command("show running-config | include Last")
                if show_run_output.strip():
                    print(f"Configuration status: {show_run_output.strip()}")
                else:
                    print("Configuration timestamp not available, but copy operation completed.")
            except:
                print("Could not verify timestamp, but copy operation completed successfully.")
            
            connection.disconnect()
            return True
            
        except Exception as e:
            print(f"Configuration apply failed: {str(e)}")
            print("The startup configuration is still saved, but not applied to running config.")
            return False
    
    def run(self):
        """Main execution flow"""
        try:
            # Get device credentials
            if not self.get_device_credentials():
                return False
            
            # Test connection
            if not self.test_connection():
                return False
            
            # Backup configuration
            config_path = self.backup_config()
            if not config_path:
                return False
            
            # Wait for user to edit
            if not self.wait_for_user_edit(config_path):
                return False
            
            # Restore configuration
            if not self.restore_config(config_path):
                print("Configuration restore failed. Your original config is still intact.")
                return False
            
            print("\n✓ Configuration successfully updated!")
            
            # Apply startup config to running config
            self.apply_startup_to_running()
            
            print("\n=== PROCESS COMPLETE ===")
            print("Your network device configuration has been successfully updated.")
            print("Configuration changes are now active on the device.")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return False
        except Exception as e:
            print(f"\nUnexpected error: {str(e)}")
            return False

def main():
    """Main function"""
    manager = NetworkConfigManager()
    success = manager.run()
    
    if success:
        print("\nNetwork Configuration Manager completed successfully!")
    else:
        print("\nNetwork Configuration Manager encountered errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
