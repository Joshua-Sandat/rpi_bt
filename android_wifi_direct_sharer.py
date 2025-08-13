#!/usr/bin/env python3
"""
Android WiFi Direct Credential Sharer for Raspberry Pi Zero 2 W
Automatically extracts WiFi credentials from Android phones using WiFi Direct
Optimized for Android devices - no iOS complexity!

This script uses WiFi Direct to automatically extract WiFi credentials
from connected Android phones when they connect via Bluetooth.

Usage:
    sudo python3 android_wifi_direct_sharer.py
"""

import os
import sys
import time
import json
import subprocess
import logging
import dbus
import dbus.mainloop.glib
from pathlib import Path
from typing import Optional, Dict, Any
from gi.repository import GLib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/android_wifi_direct_sharer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AndroidWiFiDirectSharer:
    def __init__(self):
        self.config_file = Path("/etc/wifi_credentials.json")
        self.bluetooth_service_name = "PiWiFiSetup"
        self.mainloop = None
        self.bus = None
        self.adapter = None
        self.connected_devices = set()
        self.credentials_received = False
        self.wifi_direct_interface = "p2p0"
        
    def check_dependencies(self) -> bool:
        """Check if required system packages are installed."""
        required_packages = ['bluez', 'bluez-tools', 'wpasupplicant', 'python3-dbus', 'python3-gi']
        
        missing_packages = []
        for package in required_packages:
            try:
                subprocess.run(['dpkg', '-s', package], 
                             capture_output=True, check=True)
            except subprocess.CalledProcessError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"Missing packages: {', '.join(missing_packages)}")
            logger.info("Install with: sudo apt update && sudo apt install " + 
                       " ".join(missing_packages))
            return False
        
        # Check if WiFi Direct is supported
        try:
            result = subprocess.run(['wpa_cli', 'help'], 
                                  capture_output=True, text=True, check=False)
            if 'p2p' not in result.stdout.lower():
                logger.error("WiFi Direct (P2P) not supported by wpa_cli")
                logger.error("Your Pi may not support WiFi Direct")
                return False
            logger.info("WiFi Direct (P2P) support confirmed")
        except Exception as e:
            logger.warning(f"Could not verify WiFi Direct support: {e}")
        
        return True
    
    def setup_bluetooth(self) -> bool:
        """Setup Bluetooth service for device detection."""
        try:
            # Stop existing Bluetooth service
            subprocess.run(['sudo', 'systemctl', 'stop', 'bluetooth'], 
                         capture_output=True)
            
            # Configure Bluetooth for Android compatibility
            bluetooth_config = f"""
[General]
Name = {self.bluetooth_service_name}
Class = 0x000100
DiscoverableTimeout = 0
PairableTimeout = 0
AutoEnable = true

[Policy]
AutoEnable = true
"""
            
            with open('/tmp/bluetooth.conf', 'w') as f:
                f.write(bluetooth_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/bluetooth.conf', 
                          '/etc/bluetooth/main.conf'], check=True)
            
            # Start Bluetooth service
            subprocess.run(['sudo', 'systemctl', 'start', 'bluetooth'], 
                         check=True)
            subprocess.run(['sudo', 'systemctl', 'enable', 'bluetooth'], 
                         check=True)
            
            # Make Pi discoverable and pairable
            subprocess.run(['sudo', 'bluetoothctl', 'discoverable', 'on'], 
                         check=True)
            subprocess.run(['sudo', 'bluetoothctl', 'pairable', 'on'], 
                         check=True)
            
            # Wait for Bluetooth to be ready
            time.sleep(3)
            
            logger.info("Bluetooth service configured successfully for Android")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup Bluetooth: {e}")
            return False
    
    def setup_wifi_direct(self) -> bool:
        """Setup WiFi Direct optimized for Android devices."""
        try:
            # First check if WiFi interface is available
            if not self.check_wifi_interface_status():
                logger.error("WiFi interface not available for WiFi Direct")
                return False
            
            logger.info("Cleaning up existing WiFi interfaces...")
            
            # Kill any existing wpa_supplicant processes
            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], 
                         capture_output=True, check=False)
            subprocess.run(['sudo', 'killall', 'hostapd'], 
                         capture_output=True, check=False)
            
            # Wait for processes to fully stop
            time.sleep(3)
            
            # Stop system services
            subprocess.run(['sudo', 'systemctl', 'stop', 'wpa_supplicant'], 
                         capture_output=True, check=False)
            subprocess.run(['sudo', 'systemctl', 'stop', 'networking'], 
                         capture_output=True, check=False)
            
            # Bring down wlan0 interface
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'down'], 
                         capture_output=True, check=False)
            
            # Wait for interface to be fully down
            time.sleep(2)
            
            # Bring up wlan0 interface
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], 
                         capture_output=True, check=False)
            
            # Wait for interface to be ready
            time.sleep(2)
            
            logger.info("WiFi interface cleanup completed")
            
            # Create minimal, compatible wpa_supplicant configuration
            wpa_config = f"""
ctrl_interface=/var/run/wpa_supplicant
ctrl_interface_group=0
update_config=1

# Minimal WiFi Direct configuration - compatible with all Pi versions
p2p_disabled=0
"""
            
            with open('/tmp/wpa_supplicant.conf', 'w') as f:
                f.write(wpa_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/wpa_supplicant.conf', 
                          '/etc/wpa_supplicant/wpa_supplicant.conf'], check=True)
            
            # Start wpa_supplicant with WiFi Direct support
            subprocess.run(['sudo', 'wpa_supplicant', '-B', '-i', 'wlan0', 
                          '-c', '/etc/wpa_supplicant/wpa_supplicant.conf', 
                          '-D', 'nl80211'], check=True)
            
            # Wait for WiFi Direct to be ready
            time.sleep(5)
            
            # Test if WiFi Direct is working
            try:
                result = subprocess.run(['sudo', 'wpa_cli', 'p2p_find'], 
                                      capture_output=True, text=True, check=False, timeout=10)
                
                if result.returncode == 0:
                    # Additional verification - check if P2P interface was actually created
                    time.sleep(2)
                    p2p_check = subprocess.run(['sudo', 'wpa_cli', 'p2p_peers'], 
                                             capture_output=True, text=True, check=False, timeout=5)
                    
                    if p2p_check.returncode == 0:
                        logger.info("Android-optimized WiFi Direct configured successfully")
                        return True
                    else:
                        logger.warning("WiFi Direct test passed but P2P interface not working")
                        logger.warning(f"P2P check error: {p2p_check.stderr}")
                        return self.setup_wifi_direct_fallback()
                else:
                    logger.warning(f"WiFi Direct test failed with return code {result.returncode}")
                    logger.warning(f"Error output: {result.stderr}")
                    return self.setup_wifi_direct_fallback()
                    
            except subprocess.TimeoutExpired:
                logger.warning("WiFi Direct test timed out, using fallback method")
                return self.setup_wifi_direct_fallback()
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup WiFi Direct: {e}")
            logger.info("Trying fallback method...")
            return self.setup_wifi_direct_fallback()
    
    def setup_wifi_direct_fallback(self) -> bool:
        """Fallback WiFi Direct setup for Android compatibility."""
        try:
            logger.info("Setting up WiFi Direct fallback for Android...")
            
            # Create minimal Android-compatible wpa_supplicant configuration
            wpa_config = f"""
ctrl_interface=/var/run/wpa_supplicant
ctrl_interface_group=0
update_config=1

# Minimal Android WiFi Direct configuration
p2p_disabled=0
p2p_go_intent=0
"""
            
            with open('/tmp/wpa_supplicant.conf', 'w') as f:
                f.write(wpa_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/wpa_supplicant.conf', 
                          '/etc/wpa_supplicant/wpa_supplicant.conf'], check=True)
            
            # Start wpa_supplicant with minimal config
            subprocess.run(['sudo', 'wpa_supplicant', '-B', '-i', 'wlan0', 
                          '-c', '/etc/wpa_supplicant/wpa_supplicant.conf', 
                          '-D', 'nl80211'], check=True)
            
            # Wait for wpa_supplicant to be ready
            time.sleep(5)
            
            # Try basic P2P commands
            try:
                subprocess.run(['sudo', 'wpa_cli', 'p2p_find'], check=True, timeout=5)
                logger.info("Android WiFi Direct fallback configured successfully")
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                logger.warning("Android WiFi Direct fallback also failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to setup Android WiFi Direct fallback: {e}")
            return False
    
    def setup_dbus(self) -> bool:
        """Setup D-Bus connection for Bluetooth monitoring."""
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SystemBus()
            self.mainloop = GLib.MainLoop()
            
            # Get Bluetooth adapter
            manager = dbus.Interface(
                self.bus.get_object("org.bluez", "/"),
                "org.freedesktop.DBus.ObjectManager"
            )
            
            objects = manager.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.Adapter1" in interfaces:
                    self.adapter = path
                    break
            
            if not self.adapter:
                logger.error("No Bluetooth adapter found")
                return False
            
            logger.info("D-Bus connection established")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup D-Bus: {e}")
            return False
    
    def setup_bluetooth_monitoring(self) -> bool:
        """Setup monitoring for Bluetooth connections."""
        try:
            # Monitor for device connections
            self.bus.add_signal_receiver(
                self.on_device_connected,
                signal_name="InterfacesAdded",
                dbus_interface="org.freedesktop.DBus.ObjectManager"
            )
            
            # Monitor for device disconnections
            self.bus.add_signal_receiver(
                self.on_device_disconnected,
                signal_name="InterfacesRemoved",
                dbus_interface="org.freedesktop.DBus.ObjectManager"
            )
            
            logger.info("Bluetooth monitoring setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Bluetooth monitoring: {e}")
            return False
    
    def on_device_connected(self, path, interfaces):
        """Called when a device connects via Bluetooth."""
        try:
            if "org.bluez.Device1" in interfaces:
                device = interfaces["org.bluez.Device1"]
                device_name = device.get("Name", "Unknown Device")
                device_address = device.get("Address", "Unknown")
                
                logger.info(f"Android device connected: {device_name} ({device_address})")
                self.connected_devices.add(path)
                
                # Start Android WiFi Direct credential extraction
                self.extract_wifi_credentials_from_android(device_name, device_address)
                
        except Exception as e:
            logger.error(f"Error handling device connection: {e}")
    
    def on_device_disconnected(self, path, interfaces):
        """Called when a device disconnects from Bluetooth."""
        try:
            if path in self.connected_devices:
                logger.info(f"Android device disconnected: {path}")
                self.connected_devices.remove(path)
                
        except Exception as e:
            logger.error(f"Error handling device disconnection: {e}")
    
    def extract_wifi_credentials_from_android(self, device_name: str, device_address: str) -> bool:
        """Extract WiFi credentials from Android device using WiFi Direct."""
        start_time = time.time()
        timeout_seconds = 90  # 1.5 minutes total timeout for Android
        
        try:
            logger.info(f"Starting Android WiFi Direct credential extraction from {device_name}...")
            logger.info(f"Total timeout: {timeout_seconds} seconds")
            
            # Step 1: Discover Android WiFi Direct devices
            logger.info("Step 1: Discovering Android WiFi Direct devices...")
            try:
                subprocess.run(['sudo', 'wpa_cli', 'p2p_find'], check=True, timeout=10)
                logger.info("WiFi Direct discovery started, waiting 15 seconds for Android...")
                time.sleep(15)  # Android devices need more time to respond
                
                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    logger.warning("Timeout reached during discovery")
                    return False
                    
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                logger.warning("WiFi Direct discovery failed")
                return False
            
            # Step 2: Get list of discovered Android devices
            logger.info("Step 2: Getting list of discovered Android devices...")
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_peers'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0 and result.stdout.strip():
                logger.info("Android WiFi Direct devices discovered:")
                logger.info(result.stdout)
                
                # Parse discovered Android devices
                discovered_devices = self.parse_android_devices(result.stdout)
                logger.info(f"Found {len(discovered_devices)} Android WiFi Direct devices")
                
                # Step 3: Try to connect to each discovered Android device
                for i, device_info in enumerate(discovered_devices):
                    logger.info(f"Step 3: Attempting connection to Android device {device_info.get('name', 'Unknown')} ({device_info['address']})... ({i+1}/{len(discovered_devices)})")
                    
                    # Check timeout before each connection attempt
                    if time.time() - start_time > timeout_seconds:
                        logger.warning("Timeout reached during connection attempts")
                        return False
                    
                    if self.connect_to_android_via_wifi_direct(device_info.get('name', 'Unknown'), device_info['address']):
                        logger.info("Android WiFi Direct connection successful!")
                        return True
                    else:
                        logger.info(f"Connection to {device_info.get('name', 'Unknown')} failed, trying next device...")
                        
                        # Debug current state after failed connection
                        logger.info("Debugging current state after failed connection...")
                        self.debug_android_wifi_direct_state()
            else:
                logger.info("No Android WiFi Direct devices discovered")
            
            # Step 4: Try Android-specific WiFi Direct methods
            logger.info("Step 4: Trying Android-specific WiFi Direct methods...")
            if time.time() - start_time > timeout_seconds:
                logger.warning("Timeout reached before Android-specific methods")
                return False
                
            if self.try_android_specific_methods(device_name, device_address):
                return True
            
            logger.warning("All Android WiFi Direct methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error in Android WiFi Direct credential extraction: {e}")
            return False
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"Android WiFi Direct extraction completed in {elapsed_time:.1f} seconds")
    
    def parse_android_devices(self, peers_output: str) -> list:
        """Parse the output of p2p_peers to extract Android device information."""
        devices = []
        try:
            lines = peers_output.strip().split('\n')
            current_device = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('dev_addr='):
                    if current_device and 'address' in current_device:
                        devices.append(current_device)
                    current_device = {'address': line.split('=', 1)[1]}
                elif line.startswith('dev_name='):
                    current_device['name'] = line.split('=', 1)[1]
                elif line.startswith('p2p_dev_addr='):
                    current_device['p2p_address'] = line.split('=', 1)[1]
                elif line.startswith('p2p_go_intent='):
                    current_device['go_intent'] = line.split('=', 1)[1]
                elif line.startswith('p2p_dev_capab='):
                    current_device['capabilities'] = line.split('=', 1)[1]
            
            # Add the last device if it has an address
            if current_device and 'address' in current_device:
                devices.append(current_device)
            
            logger.info(f"Parsed {len(devices)} Android devices from discovery output")
            for device in devices:
                logger.info(f"  - {device.get('name', 'Unknown')} ({device.get('address', 'Unknown')})")
                
        except Exception as e:
            logger.error(f"Error parsing Android devices: {e}")
            logger.error(f"Raw output was: {peers_output}")
        
        return devices
    
    def connect_to_android_via_wifi_direct(self, device_name: str, device_address: str) -> bool:
        """Attempt to connect to Android phone via WiFi Direct."""
        try:
            logger.info(f"Attempting WiFi Direct connection to Android device {device_name} ({device_address})...")
            
            # Try to connect using device address with PBC (Push Button Configuration)
            logger.info("Initiating P2P connection with PBC (Android compatible)...")
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_connect', device_address, 'pbc'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                logger.info("Android WiFi Direct connection initiated!")
                logger.info(f"Connection output: {result.stdout}")
                
                # Wait for connection with progress updates (Android devices may take longer)
                logger.info("Waiting for Android connection to establish...")
                for i in range(45):  # Wait up to 45 seconds for Android
                    time.sleep(1)
                    if i % 5 == 0:  # Progress update every 5 seconds
                        logger.info(f"Android connection attempt in progress... ({i+1}/45 seconds)")
                    
                    # Check connection status
                    if self.check_android_wifi_direct_connection():
                        logger.info("Android WiFi Direct connection established!")
                        return self.extract_credentials_from_android_wifi_direct()
                
                logger.warning("Android connection attempt timed out after 45 seconds")
                return False
            else:
                logger.error(f"Failed to initiate Android connection: {result.stderr}")
                return False
            
        except Exception as e:
            logger.error(f"Error connecting to Android via WiFi Direct: {e}")
            return False
    
    def try_android_specific_methods(self, device_name: str, device_address: str) -> bool:
        """Try Android-specific WiFi Direct methods for credential extraction."""
        try:
            logger.info("Trying Android-specific WiFi Direct methods...")
            
            # Method 1: Android WiFi Direct service discovery
            logger.info("Method 1: Android WiFi Direct service discovery...")
            
            # Send service discovery request (Android compatible)
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_serv_disc_req', 
                                   device_address, '02000001'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                logger.info("Android service discovery request sent")
                time.sleep(10)  # Android devices need more time
                
                # Check for service responses
                if self.check_for_android_service_responses():
                    return True
            
            # Method 2: Android WiFi Direct group formation
            logger.info("Method 2: Android WiFi Direct group formation...")
            
            # Try to form a group with the Android device
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_group_add'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                logger.info("Android WiFi Direct group formation initiated")
                time.sleep(15)  # Wait for group formation
                
                # Check group status
                if self.check_android_group_status():
                    return True
            
            # Method 3: Direct Android credential extraction
            logger.info("Method 3: Direct Android credential extraction...")
            
            return self.direct_android_extraction(device_name, device_address)
            
        except Exception as e:
            logger.error(f"Error in Android-specific WiFi Direct methods: {e}")
            return False
    
    def check_android_wifi_direct_connection(self) -> bool:
        """Check if Android WiFi Direct connection is established."""
        try:
            result = subprocess.run(['sudo', 'wpa_cli', 'status'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                status = result.stdout
                logger.debug(f"Current Android wpa_supplicant status: {status}")
                
                if 'p2p_go_mode=1' in status or 'p2p_client_mode=1' in status:
                    logger.info("Android WiFi Direct connection established!")
                    return True
                elif 'p2p' in status.lower():
                    logger.info("Android WiFi Direct is active but not fully connected")
                    logger.info(f"P2P status: {status}")
                    return False
                else:
                    logger.debug("No Android WiFi Direct activity detected")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking Android WiFi Direct connection: {e}")
            return False
    
    def check_for_android_service_responses(self) -> bool:
        """Check for Android WiFi Direct service responses."""
        try:
            # Check for service responses
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_serv_disc_resp'], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and result.stdout.strip():
                logger.info("Android service discovery responses received:")
                logger.info(result.stdout)
                return True
            elif result.returncode != 0:
                logger.info(f"Service discovery response check returned {result.returncode}: {result.stderr}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for Android service responses: {e}")
            return False
    
    def check_android_group_status(self) -> bool:
        """Check Android WiFi Direct group status."""
        try:
            # Check group information
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_group_info'], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and result.stdout.strip():
                logger.info("Android WiFi Direct group status:")
                logger.info(result.stdout)
                
                # Look for group formation success
                if 'group_id=' in result.stdout:
                    logger.info("Android WiFi Direct group formed successfully!")
                    return True
            elif result.returncode != 0:
                logger.info(f"Group status check returned {result.returncode}: {result.stderr}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking Android group status: {e}")
            return False
    
    def direct_android_extraction(self, device_name: str, device_address: str) -> bool:
        """Attempt direct credential extraction from Android device."""
        try:
            logger.info("Attempting direct Android credential extraction...")
            
            # Try to get Android device information
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_peer', device_address], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                logger.info("Android device information retrieved:")
                logger.info(result.stdout)
                
                # Look for network information in Android device details
                if self.parse_android_network_info(result.stdout):
                    return True
            
            # Try to request specific network information from Android
            logger.info("Requesting specific network information from Android...")
            
            # Send network query request (Android compatible)
            subprocess.run(['sudo', 'wpa_cli', 'p2p_serv_disc_req', 
                          device_address, '02000001'], check=True)
            
            time.sleep(10)  # Android devices need more time
            
            # Check for network information
            if self.check_for_android_network_info():
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in direct Android extraction: {e}")
            return False
    
    def parse_android_network_info(self, device_info: str) -> bool:
        """Parse network information from Android device details."""
        try:
            # Look for Android-specific network information
            android_network_indicators = ['network', 'ssid', 'wifi', 'hotspot', 'tethering']
            
            for indicator in android_network_indicators:
                if indicator in device_info.lower():
                    logger.info(f"Android network information found: {indicator}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error parsing Android network info: {e}")
            return False
    
    def check_for_android_network_info(self) -> bool:
        """Check for network information from Android responses."""
        try:
            # Check various sources for Android network information
            sources = [
                ['sudo', 'wpa_cli', 'p2p_peers'],
                ['sudo', 'wpa_cli', 'status'],
                ['sudo', 'wpa_cli', 'list_networks']
            ]
            
            for source in sources:
                try:
                    result = subprocess.run(source, capture_output=True, text=True, check=True)
                    if result.returncode == 0 and result.stdout.strip():
                        android_indicators = ['network', 'ssid', 'wifi', 'android', 'p2p']
                        for indicator in android_indicators:
                            if indicator in result.stdout.lower():
                                logger.info(f"Android network information found in {source[-1]}:")
                                logger.info(result.stdout)
                                return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for Android network info: {e}")
            return False
    
    def extract_credentials_from_android_wifi_direct(self) -> bool:
        """Extract credentials from established Android WiFi Direct connection."""
        try:
            logger.info("Extracting credentials from Android WiFi Direct connection...")
            
            # Get connection information
            result = subprocess.run(['sudo', 'wpa_cli', 'status'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                status = result.stdout
                logger.info("Android WiFi Direct connection status:")
                logger.info(status)
                
                # Look for network information
                if self.extract_android_network_credentials(status):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error extracting credentials from Android WiFi Direct: {e}")
            return False
    
    def extract_android_network_credentials(self, status: str) -> bool:
        """Extract network credentials from Android WiFi Direct status."""
        try:
            # Parse status for Android network information
            lines = status.split('\n')
            network_info = {}
            
            for line in lines:
                if '=' in line:
                    key, value = line.split('=', 1)
                    network_info[key.strip()] = value.strip()
            
            # Look for Android network credentials
            if 'ssid' in network_info or 'psk' in network_info:
                logger.info("Android network credentials found!")
                logger.info(f"Network info: {network_info}")
                
                # Extract SSID and password
                ssid = network_info.get('ssid', 'Unknown')
                password = network_info.get('psk', 'Unknown')
                
                if ssid != 'Unknown' and password != 'Unknown':
                    logger.info(f"Android WiFi credentials extracted via WiFi Direct!")
                    logger.info(f"SSID: {ssid}")
                    logger.info(f"Password: {password}")
                    
                    # Save credentials
                    credentials = {'ssid': ssid, 'password': password}
                    with open(self.config_file, 'w') as f:
                        json.dump(credentials, f)
                    
                    self.credentials_received = True
                    
                    # Now connect to the extracted network
                    if self.connect_to_extracted_network(ssid, password):
                        logger.info("Successfully connected to extracted Android WiFi network!")
                        return True
                    else:
                        logger.warning("Failed to connect to extracted network")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error extracting Android network credentials: {e}")
            return False
    
    def connect_to_extracted_network(self, ssid: str, password: str) -> bool:
        """Connect to the extracted WiFi network."""
        try:
            logger.info(f"Connecting to extracted network: {ssid}")
            
            # Stop WiFi Direct services
            subprocess.run(['sudo', 'wpa_cli', 'p2p_stop_find'], check=True)
            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], check=True)
            
            # Create standard WiFi client configuration
            wpa_config = f"""
ctrl_interface=/var/run/wpa_supplicant
ctrl_interface_group=0
update_config=1

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
    scan_ssid=1
}}
"""
            
            with open('/tmp/wpa_supplicant_client.conf', 'w') as f:
                f.write(wpa_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/wpa_supplicant_client.conf', 
                          '/etc/wpa_supplicant/wpa_supplicant.conf'], check=True)
            
            # Start wpa_supplicant in client mode
            subprocess.run(['sudo', 'wpa_supplicant', '-B', '-i', 'wlan0', 
                          '-c', '/etc/wpa_supplicant/wpa_supplicant.conf', 
                          '-D', 'nl80211'], check=True)
            
            # Wait for connection
            time.sleep(10)
            
            # Check connection status
            if self.check_wifi_connection():
                logger.info("Successfully connected to WiFi network!")
                return True
            else:
                logger.warning("Failed to connect to WiFi network")
                return False
            
        except Exception as e:
            logger.error(f"Error connecting to extracted network: {e}")
            return False
    
    def check_wifi_connection(self) -> bool:
        """Check if WiFi connection is established."""
        try:
            result = subprocess.run(['iwconfig', 'wlan0'], 
                                  capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                output = result.stdout
                if 'ESSID:' in output and 'Not-Associated' not in output:
                    logger.info("WiFi connection established!")
                    logger.info(f"Connection status: {output}")
                    return True
                else:
                    logger.info("WiFi not yet connected")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking WiFi connection: {e}")
            return False
    
    def debug_android_wifi_direct_state(self):
        """Debug the current Android WiFi Direct state."""
        logger.info("🔍 Debugging Android WiFi Direct state...")
        
        try:
            # Check wpa_supplicant status
            result = subprocess.run(['sudo', 'wpa_cli', 'status'], 
                                  capture_output=True, text=True, check=True)
            if result.returncode == 0:
                logger.info("WPA Status:")
                logger.info(result.stdout)
            
            # Check P2P peers
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_peers'], 
                                  capture_output=True, text=True, check=True)
            if result.returncode == 0:
                logger.info("P2P Peers:")
                logger.info(result.stdout)
            
            # Check P2P groups
            result = subprocess.run(['sudo', 'wpa_cli', 'p2p_group_info'], 
                                  capture_output=True, text=True, check=True)
            if result.returncode == 0:
                logger.info("P2P Groups:")
                logger.info(result.stdout)
            
            # Check network interfaces
            result = subprocess.run(['ip', 'addr', 'show'], 
                                  capture_output=True, text=True, check=True)
            if result.returncode == 0:
                logger.info("Network Interfaces:")
                logger.info(result.stdout)
                
        except Exception as e:
            logger.error(f"Error getting Android WiFi Direct status: {e}")
        
        logger.info("🔍 Android WiFi Direct debug complete")
    
    def check_wifi_interface_status(self) -> bool:
        """Check if WiFi interface is available and not busy."""
        try:
            # Check if wlan0 exists
            result = subprocess.run(['ip', 'link', 'show', 'wlan0'], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                logger.error("wlan0 interface not found")
                return False
            
            # Check if interface is up
            if 'UP' not in result.stdout:
                logger.warning("wlan0 interface is down")
                return False
            
            # Check if interface is busy
            result = subprocess.run(['iwconfig', 'wlan0'], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                if 'ESSID:' in result.stdout and 'Not-Associated' not in result.stdout:
                    logger.warning("wlan0 is currently connected to a network")
                    return False
                elif 'Mode:' in result.stdout and 'Master' in result.stdout:
                    logger.warning("wlan0 is currently in AP mode")
                    return False
            
            logger.info("WiFi interface status check passed")
            return True
            
        except Exception as e:
            logger.error(f"Error checking WiFi interface status: {e}")
            return False
    
    def run(self):
        """Main execution flow for Android devices."""
        logger.info("Starting Android WiFi Direct Credential Sharer...")
        logger.info("This will automatically extract WiFi credentials from Android phones!")
        logger.info("Optimized for Android devices - no iOS complexity!")
        
        try:
            # Check dependencies
            if not self.check_dependencies():
                logger.error("Dependencies not met. Exiting.")
                return False
            
            # Setup Bluetooth
            if not self.setup_bluetooth():
                logger.error("Failed to setup Bluetooth")
                return False
            
            # Setup WiFi Direct (Android-optimized)
            logger.info("Setting up Android-optimized WiFi Direct...")
            if not self.setup_wifi_direct():
                logger.error("Android WiFi Direct setup failed")
                logger.error("WiFi Direct is required for credential extraction")
                logger.error("Please check your Pi's WiFi Direct capabilities")
                return False
            
            # Setup D-Bus
            if not self.setup_dbus():
                logger.error("Failed to setup D-Bus")
                return False
            
            # Setup Bluetooth monitoring
            if not self.setup_bluetooth_monitoring():
                logger.error("Failed to setup Bluetooth monitoring")
                return False
            
            logger.info("Android setup complete! Waiting for Android phone to connect...")
            logger.info("On your Android phone:")
            logger.info("1. Go to Bluetooth settings")
            logger.info("2. Connect to 'PiWiFiSetup'")
            logger.info("3. Pi will attempt WiFi Direct credential extraction")
            logger.info("4. Android should show WiFi Direct connection prompt")
            logger.info("")
            logger.info("🔍 How the Android system works:")
            logger.info("  - Pi connects to Android phone via Bluetooth")
            logger.info("  - Pi initiates WiFi Direct connection request")
            logger.info("  - Android shows WiFi Direct connection prompt")
            logger.info("  - Android shares WiFi credentials automatically")
            logger.info("  - Pi connects to your home WiFi network")
            
            # Start the main loop to monitor for connections
            self.mainloop.run()
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            return True
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

def main():
    """Main entry point."""
    # Check if running as root
    if os.geteuid() != 0:
        logger.error("This script must be run as root (use sudo)")
        sys.exit(1)
    
    sharer = AndroidWiFiDirectSharer()
    success = sharer.run()
    
    if success:
        logger.info("Android WiFi Direct credential sharing completed successfully!")
        sys.exit(0)
    else:
        logger.error("Android WiFi Direct credential sharing failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
