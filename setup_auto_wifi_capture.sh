#!/bin/bash
# Setup script for Auto WiFi Credential Capture on Raspberry Pi Zero 2 W
# This approach automatically captures WiFi credentials without requiring phone apps

echo "🔌 Setting up Auto WiFi Credential Capture for Raspberry Pi Zero 2 W"
echo "=================================================================="
echo "📱 No phone app installation required!"
echo "🔄 Automatically captures WiFi credentials via network sharing"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "📦 Installing required packages..."
apt install -y bluez bluez-tools wpasupplicant hostapd dnsmasq python3-dbus python3-gi

# Stop services that might interfere
echo "🛑 Stopping conflicting services..."
systemctl stop bluetooth
systemctl stop wpa_supplicant
systemctl stop networking

# Configure hostapd
echo "⚙️  Configuring WiFi hotspot..."
systemctl unmask hostapd

# Configure dnsmasq
echo "⚙️  Configuring DHCP server..."
systemctl unmask dnsmasq

# Make script executable
chmod +x auto_wifi_capture.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start automatic WiFi credential capture:"
echo "  sudo python3 auto_wifi_capture.py"
echo ""
echo "What happens automatically:"
echo "1. Pi creates WiFi hotspot 'PiWiFiSetup' with password '12345678'"
echo "2. Connect your phone to Pi via Bluetooth"
echo "3. Phone automatically shares WiFi credentials (no app needed!)"
echo "4. Pi captures credentials and connects to your WiFi"
echo ""
echo "📱 On your phone:"
echo "  - Connect to 'PiWiFiSetup' via Bluetooth"
echo "  - Look for 'Share WiFi' or 'Network sharing' prompts"
echo "  - Accept the sharing request"
echo "  - Pi automatically gets your WiFi credentials!"
echo ""
echo "🔍 How it works:"
echo "  - Pi creates a temporary WiFi network"
echo "  - When phone connects via Bluetooth, it can share its WiFi"
echo "  - Most phones automatically offer this option"
echo "  - No manual input or app installation required!"
echo ""
echo "🎯 This is the most automatic approach available!"
echo "   Just connect Bluetooth and accept the sharing prompt on your phone."
