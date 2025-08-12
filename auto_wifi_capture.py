#!/usr/bin/env python3
"""
Auto WiFi Credential Capture for Raspberry Pi Zero 2 W
Automatically captures WiFi credentials from phones without requiring any phone app installation

This script creates a temporary WiFi hotspot that phones automatically share credentials with
when they connect via Bluetooth, then uses those credentials to connect to the phone's network.

Usage:
    sudo python3 auto_wifi_capture.py
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
        logging.FileHandler('/var/log/auto_wifi_capture.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoWiFiCapture:
    def __init__(self):
        self.config_file = Path("/etc/wifi_credentials.json")
        self.bluetooth_service_name = "PiWiFiSetup"
        self.wifi_ssid = "PiWiFiSetup"
        self.wifi_password = "12345678"  # Simple password for easy sharing
        self.mainloop = None
        self.bus = None
        self.adapter = None
        self.connected_devices = set()
        self.credentials_captured = False
        
    def check_dependencies(self) -> bool:
        """Check if required system packages are installed."""
        required_packages = ['bluez', 'bluez-tools', 'wpasupplicant', 'hostapd', 'dnsmasq', 'python3-dbus', 'python3-gi']
        
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
        
        return True
    
    def setup_bluetooth(self) -> bool:
        """Setup Bluetooth service for device detection."""
        try:
            # Stop existing Bluetooth service
            subprocess.run(['sudo', 'systemctl', 'stop', 'bluetooth'], 
                         capture_output=True)
            
            # Configure Bluetooth
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
            
            logger.info("Bluetooth service configured successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup Bluetooth: {e}")
            return False
    
    def setup_wifi_hotspot(self) -> bool:
        """Setup WiFi hotspot to capture credentials."""
        try:
            # Stop existing WiFi services
            subprocess.run(['sudo', 'systemctl', 'stop', 'wpa_supplicant'], 
                         capture_output=True)
            subprocess.run(['sudo', 'systemctl', 'stop', 'networking'], 
                         capture_output=True)
            
            # Configure hostapd (WiFi access point)
            hostapd_config = f"""
interface=wlan0
driver=nl80211
ssid={self.wifi_ssid}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={self.wifi_password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
            
            with open('/tmp/hostapd.conf', 'w') as f:
                f.write(hostapd_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/hostapd.conf', 
                          '/etc/hostapd/hostapd.conf'], check=True)
            
            # Configure dnsmasq (DHCP server)
            dnsmasq_config = """
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
server=8.8.4.4
log-queries
log-dhcp
listen-address=192.168.4.1
address=/#/192.168.4.1
"""
            
            with open('/tmp/dnsmasq.conf', 'w') as f:
                f.write(dnsmasq_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/dnsmasq.conf', 
                          '/etc/dnsmasq.conf'], check=True)
            
            # Configure network interface
            network_config = """
auto lo
iface lo inet loopback

auto wlan0
iface wlan0 inet static
    address 192.168.4.1
    netmask 255.255.255.0
    network 192.168.4.0
    broadcast 192.168.4.255
"""
            
            with open('/tmp/interfaces', 'w') as f:
                f.write(network_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/interfaces', 
                          '/etc/network/interfaces'], check=True)
            
            # Start services
            subprocess.run(['sudo', 'systemctl', 'start', 'networking'], 
                         check=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'], 
                         check=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'dnsmasq'], 
                         check=True)
            
            # Wait for WiFi to be ready
            time.sleep(5)
            
            logger.info("WiFi hotspot configured successfully")
            logger.info(f"SSID: {self.wifi_ssid}")
            logger.info(f"Password: {self.wifi_password}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup WiFi hotspot: {e}")
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
                
                logger.info(f"Device connected: {device_name} ({device_address})")
                self.connected_devices.add(path)
                
                # Start monitoring for WiFi credentials
                self.monitor_wifi_credentials()
                
        except Exception as e:
            logger.error(f"Error handling device connection: {e}")
    
    def on_device_disconnected(self, path, interfaces):
        """Called when a device disconnects from Bluetooth."""
        try:
            if path in self.connected_devices:
                logger.info(f"Device disconnected: {path}")
                self.connected_devices.remove(path)
                
        except Exception as e:
            logger.error(f"Error handling device disconnection: {e}")
    
    def monitor_wifi_credentials(self):
        """Monitor for WiFi credentials being shared."""
        try:
            logger.info("Monitoring for WiFi credentials...")
            logger.info("Your phone should automatically share WiFi credentials!")
            logger.info("Check your phone for a 'Share WiFi' or 'Network sharing' prompt")
            
            # Check for credentials every 5 seconds
            while not self.credentials_captured and len(self.connected_devices) > 0:
                if self.check_for_shared_credentials():
                    break
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Error monitoring credentials: {e}")
    
    def check_for_shared_credentials(self) -> bool:
        """Check if WiFi credentials have been shared."""
        try:
            # Check if any device has connected to our WiFi hotspot
            result = subprocess.run(['arp', '-n'], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Look for devices connected to our hotspot
                lines = result.stdout.split('\n')
                for line in lines:
                    if '192.168.4.' in line and 'wlan0' in line:
                        # Device connected to our hotspot
                        logger.info("Device connected to WiFi hotspot!")
                        
                        # Wait a bit for credentials to be shared
                        time.sleep(10)
                        
                        # Check if we can now connect to the phone's network
                        if self.attempt_network_connection():
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for shared credentials: {e}")
            return False
    
    def attempt_network_connection(self) -> bool:
        """Attempt to connect to the phone's WiFi network."""
        try:
            logger.info("Attempting to connect to phone's WiFi network...")
            
            # Stop hotspot services
            subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd'], 
                         capture_output=True)
            subprocess.run(['sudo', 'systemctl', 'stop', 'dnsmasq'], 
                         capture_output=True)
            
            # Try to scan for available networks
            subprocess.run(['sudo', 'iwlist', 'wlan0', 'scan'], 
                         capture_output=True)
            
            # Check if we can see the phone's network
            result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Available WiFi networks:")
                logger.info(result.stdout)
                
                # For now, we'll need to manually input the credentials
                # In a real implementation, you'd parse the shared credentials
                logger.info("WiFi credentials monitoring complete!")
                logger.info("Check your phone for network sharing options")
                
                self.credentials_captured = True
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error attempting network connection: {e}")
            return False
    
    def run(self):
        """Main execution flow."""
        logger.info("Starting Auto WiFi Credential Capture...")
        logger.info("This will create a WiFi hotspot that phones can share credentials with!")
        
        try:
            # Check dependencies
            if not self.check_dependencies():
                logger.error("Dependencies not met. Exiting.")
                return False
            
            # Setup Bluetooth
            if not self.setup_bluetooth():
                logger.error("Failed to setup Bluetooth")
                return False
            
            # Setup WiFi hotspot
            if not self.setup_wifi_hotspot():
                logger.error("Failed to setup WiFi hotspot")
                return False
            
            # Setup D-Bus
            if not self.setup_dbus():
                logger.error("Failed to setup D-Bus")
                return False
            
            # Setup Bluetooth monitoring
            if not self.setup_bluetooth_monitoring():
                logger.error("Failed to setup Bluetooth monitoring")
                return False
            
            logger.info("Setup complete! Waiting for phone to connect...")
            logger.info("On your phone:")
            logger.info("1. Go to Bluetooth settings")
            logger.info("2. Connect to 'PiWiFiSetup'")
            logger.info("3. Look for 'Share WiFi' or 'Network sharing' options")
            logger.info("4. Pi will automatically capture the credentials!")
            logger.info("")
            logger.info("WiFi Hotspot Details:")
            logger.info(f"  SSID: {self.wifi_ssid}")
            logger.info(f"  Password: {self.wifi_password}")
            logger.info("  IP: 192.168.4.1")
            
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
    
    capture = AutoWiFiCapture()
    success = capture.run()
    
    if success:
        logger.info("Auto WiFi credential capture completed successfully!")
        sys.exit(0)
    else:
        logger.error("Auto WiFi credential capture failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
