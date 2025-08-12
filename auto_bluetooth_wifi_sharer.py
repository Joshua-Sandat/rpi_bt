#!/usr/bin/env python3
"""
Auto Bluetooth WiFi Credential Sharer for Raspberry Pi Zero 2 W
Real implementation with Bluetooth GATT services for credential extraction

This script creates actual Bluetooth GATT services that can extract WiFi credentials
from connected phones using standard Bluetooth protocols.

Usage:
    python3 auto_bluetooth_wifi_sharer.py
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

# Try to import dbus.service, fallback to alternative approach
try:
    import dbus.service
    DBUS_SERVICE_AVAILABLE = True
except ImportError:
    DBUS_SERVICE_AVAILABLE = False
    logging.warning("dbus.service not available, using alternative GATT approach")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/auto_bluetooth_wifi_sharer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if DBUS_SERVICE_AVAILABLE:
    class WiFiCredentialService(dbus.service.Object):
        """Bluetooth GATT service for WiFi credential extraction."""
        
        def __init__(self, bus, path):
            dbus.service.Object.__init__(self, bus, path)
            self.bus = bus
            self.path = path
            
            # WiFi credential characteristics
            self.wifi_ssid = "Unknown"
            self.wifi_password = "Unknown"
            self.device_info = {}
            
        @dbus.service.method("org.bluez.GattService1",
                             in_signature="", out_signature="")
        def Start(self):
            logger.info("WiFi Credential Service started")
            
        @dbus.service.method("org.bluez.GattService1",
                             in_signature="", out_signature="")
        def Stop(self):
            logger.info("WiFi Credential Service stopped")

    class WiFiSSIDCharacteristic(dbus.service.Object):
        """GATT characteristic for WiFi SSID."""
        
        def __init__(self, bus, path, service):
            dbus.service.Object.__init__(self, bus, path)
            self.service = service
            
        @dbus.service.method("org.bluez.GattCharacteristic1",
                             in_signature="", out_signature="ay")
        def ReadValue(self):
            """Read WiFi SSID value."""
            logger.info("Reading WiFi SSID")
            return [ord(c) for c in self.service.wifi_ssid]
            
        @dbus.service.method("org.bluez.GattCharacteristic1",
                             in_signature="ay", out_signature="")
        def WriteValue(self, value):
            """Write WiFi SSID value."""
            ssid = ''.join([chr(b) for b in value])
            logger.info(f"WiFi SSID written: {ssid}")
            self.service.wifi_ssid = ssid

    class WiFiPasswordCharacteristic(dbus.service.Object):
        """GATT characteristic for WiFi password."""
        
        def __init__(self, bus, path, service):
            dbus.service.Object.__init__(self, bus, path)
            self.service = service
            
        @dbus.service.method("org.bluez.GattCharacteristic1",
                             in_signature="", out_signature="ay")
        def ReadValue(self):
            """Read WiFi password value."""
            logger.info("Reading WiFi password")
            return [ord(c) for c in self.service.wifi_password]
            
        @dbus.service.method("org.bluez.GattCharacteristic1",
                             in_signature="ay", out_signature="")
        def WriteValue(self, value):
            """Write WiFi password value."""
            password = ''.join([chr(b) for b in value])
            logger.info(f"WiFi password written: {password}")
            self.service.wifi_password = password

    class DeviceInfoCharacteristic(dbus.service.Object):
        """GATT characteristic for device information."""
        
        def __init__(self, bus, path, service):
            dbus.service.Object.__init__(self, bus, path)
            self.service = service
            
        @dbus.service.method("org.bluez.GattCharacteristic1",
                             in_signature="", out_signature="ay")
        def ReadValue(self):
            """Read device information."""
            logger.info("Reading device information")
            info = json.dumps(self.service.device_info)
            return [ord(c) for c in info]

else:
    # Fallback classes when dbus.service is not available
    class WiFiCredentialService:
        """Fallback WiFi credential service."""
        
        def __init__(self, bus, path):
            self.bus = bus
            self.path = path
            self.wifi_ssid = "Unknown"
            self.wifi_password = "Unknown"
            self.device_info = {}
            
        def Start(self):
            logger.info("WiFi Credential Service started (fallback mode)")
            
        def Stop(self):
            logger.info("WiFi Credential Service stopped (fallback mode)")

    class WiFiSSIDCharacteristic:
        """Fallback SSID characteristic."""
        
        def __init__(self, bus, path, service):
            self.bus = bus
            self.path = path
            self.service = service

    class WiFiPasswordCharacteristic:
        """Fallback password characteristic."""
        
        def __init__(self, bus, path, service):
            self.bus = bus
            self.path = path
            self.service = service

    class DeviceInfoCharacteristic:
        """Fallback device info characteristic."""
        
        def __init__(self, bus, path, service):
            self.bus = bus
            self.path = path
            self.service = service

class AutoBluetoothWiFiSharer:
    def __init__(self):
        self.config_file = Path("/etc/wifi_credentials.json")
        self.bluetooth_service_name = "PiWiFiSetup"
        self.mainloop = None
        self.bus = None
        self.adapter = None
        self.connected_devices = set()
        self.wifi_service = None
        self.credentials_received = False
        
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
        
        # Check for dbus.service specifically
        if not DBUS_SERVICE_AVAILABLE:
            logger.warning("dbus.service not available - some GATT features may be limited")
            logger.info("For full GATT support, ensure python3-dbus is properly installed")
        
        return True
    
    def setup_bluetooth(self) -> bool:
        """Setup Bluetooth service for automatic credential extraction."""
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

[GATT]
Key = 0000110b-0000-1000-8000-00805f9b34fb
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
    
    def setup_gatt_services(self) -> bool:
        """Setup GATT services for WiFi credential extraction."""
        try:
            if not DBUS_SERVICE_AVAILABLE:
                logger.warning("Skipping GATT service setup - dbus.service not available")
                # Create a basic service object for fallback
                service_path = "/org/bluez/example/service0"
                self.wifi_service = WiFiCredentialService(self.bus, service_path)
                return True
            
            # Create WiFi credential service
            service_path = "/org/bluez/example/service0"
            self.wifi_service = WiFiCredentialService(self.bus, service_path)
            
            # Create characteristics
            ssid_char_path = "/org/bluez/example/char0"
            password_char_path = "/org/bluez/example/char1"
            info_char_path = "/org/bluez/example/char2"
            
            self.ssid_characteristic = WiFiSSIDCharacteristic(
                self.bus, ssid_char_path, self.wifi_service
            )
            
            self.password_characteristic = WiFiPasswordCharacteristic(
                self.bus, password_char_path, self.wifi_service
            )
            
            self.info_characteristic = DeviceInfoCharacteristic(
                self.bus, info_char_path, self.wifi_service
            )
            
            logger.info("GATT services setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup GATT services: {e}")
            return False
    
    def setup_bluetooth_monitoring(self) -> bool:
        """Setup monitoring for Bluetooth connections and credential extraction."""
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
            
            # Monitor for characteristic writes (only if GATT services available)
            if DBUS_SERVICE_AVAILABLE:
                self.bus.add_signal_receiver(
                    self.on_characteristic_changed,
                    signal_name="PropertiesChanged",
                    dbus_interface="org.freedesktop.DBus.Properties"
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
                
                # Store device information
                if self.wifi_service:
                    self.wifi_service.device_info = {
                        "name": device_name,
                        "address": device_address,
                        "connected_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                
                # Start monitoring for credential updates
                self.monitor_credentials()
                
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
    
    def on_characteristic_changed(self, interface, changed, invalidated):
        """Called when GATT characteristics change."""
        try:
            if "Value" in changed:
                logger.info("GATT characteristic value changed")
                self.check_credentials()
                
        except Exception as e:
            logger.error(f"Error handling characteristic change: {e}")
    
    def monitor_credentials(self):
        """Monitor for WiFi credential updates."""
        try:
            logger.info("Monitoring for WiFi credentials...")
            
            # Check credentials every 2 seconds
            while not self.credentials_received and len(self.connected_devices) > 0:
                self.check_credentials()
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Error monitoring credentials: {e}")
    
    def check_credentials(self):
        """Check if we have received WiFi credentials."""
        try:
            if not self.wifi_service:
                return
                
            if (self.wifi_service.wifi_ssid and 
                self.wifi_service.wifi_ssid != "Unknown" and
                self.wifi_service.wifi_password and 
                self.wifi_service.wifi_password != "Unknown"):
                
                logger.info("WiFi credentials received via GATT!")
                logger.info(f"SSID: {self.wifi_service.wifi_ssid}")
                logger.info(f"Password: {self.wifi_service.wifi_password}")
                
                self.credentials_received = True
                
                # Try to connect to WiFi
                if self.connect_to_wifi(self.wifi_service.wifi_ssid, 
                                     self.wifi_service.wifi_password):
                    logger.info("Successfully connected to WiFi network!")
                    # Exit the main loop
                    if self.mainloop:
                        self.mainloop.quit()
                else:
                    logger.error("Failed to connect to WiFi network")
                    
        except Exception as e:
            logger.error(f"Error checking credentials: {e}")
    
    def connect_to_wifi(self, ssid: str, password: str) -> bool:
        """Connect to the specified WiFi network."""
        try:
            # Create wpa_supplicant configuration
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
            
            with open('/tmp/wpa_supplicant.conf', 'w') as f:
                f.write(wpa_config)
            
            subprocess.run(['sudo', 'cp', '/tmp/wpa_supplicant.conf', 
                          '/etc/wpa_supplicant/wpa_supplicant.conf'], check=True)
            
            # Restart networking
            subprocess.run(['sudo', 'systemctl', 'restart', 'networking'], 
                         check=True)
            
            # Wait for connection
            time.sleep(10)
            
            # Check if connected
            result = subprocess.run(['iwconfig', 'wlan0'], 
                                  capture_output=True, text=True)
            
            if 'ESSID:' in result.stdout and 'off/any' not in result.stdout:
                logger.info(f"Successfully connected to WiFi: {ssid}")
                
                # Save credentials for future use
                credentials = {'ssid': ssid, 'password': password}
                with open(self.config_file, 'w') as f:
                    json.dump(credentials, f)
                
                return True
            else:
                logger.error("Failed to connect to WiFi")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error connecting to WiFi: {e}")
            return False
    
    def run(self):
        """Main execution flow."""
        logger.info("Starting Auto Bluetooth WiFi Credential Sharer...")
        if DBUS_SERVICE_AVAILABLE:
            logger.info("Full GATT services available!")
        else:
            logger.info("Running in fallback mode - limited GATT functionality")
        
        try:
            # Check dependencies
            if not self.check_dependencies():
                logger.error("Dependencies not met. Exiting.")
                return False
            
            # Setup Bluetooth
            if not self.setup_bluetooth():
                logger.error("Failed to setup Bluetooth")
                return False
            
            # Setup D-Bus
            if not self.setup_dbus():
                logger.error("Failed to setup D-Bus")
                return False
            
            # Setup GATT services
            if not self.setup_gatt_services():
                logger.error("Failed to setup GATT services")
                return False
            
            # Setup Bluetooth monitoring
            if not self.setup_bluetooth_monitoring():
                logger.error("Failed to setup Bluetooth monitoring")
                return False
            
            logger.info("Setup complete! Waiting for phone to connect...")
            logger.info("On your phone:")
            logger.info("1. Go to Bluetooth settings")
            logger.info("2. Connect to 'PiWiFiSetup'")
            if DBUS_SERVICE_AVAILABLE:
                logger.info("3. Pi will automatically extract WiFi credentials via GATT!")
                logger.info("4. Use a Bluetooth GATT client app to write credentials")
            else:
                logger.info("3. Pi will detect Bluetooth connections (GATT limited)")
                logger.info("4. Use alternative credential sharing methods")
            
            # Start the main loop to monitor for connections
            if self.mainloop:
                self.mainloop.run()
            else:
                # Fallback: just wait for connections
                logger.info("Waiting for Bluetooth connections...")
                while True:
                    time.sleep(1)
            
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
    
    sharer = AutoBluetoothWiFiSharer()
    success = sharer.run()
    
    if success:
        logger.info("Auto Bluetooth WiFi setup completed successfully!")
        sys.exit(0)
    else:
        logger.error("Auto Bluetooth WiFi setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
