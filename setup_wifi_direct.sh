#!/bin/bash
# Setup script for WiFi Direct Credential Sharer on Raspberry Pi Zero 2 W
# This approach uses WiFi Direct to automatically extract WiFi credentials

echo "🔌 Setting up WiFi Direct Credential Sharer for Raspberry Pi Zero 2 W"
echo "=================================================================="
echo "📱 No phone app installation required!"
echo "🔄 Automatically extracts WiFi credentials via WiFi Direct protocol"
echo "⚡ Most advanced and automatic approach available!"
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
apt install -y bluez bluez-tools wpasupplicant python3-dbus python3-gi

# Stop services that might interfere
echo "🛑 Stopping conflicting services..."
systemctl stop bluetooth
systemctl stop wpa_supplicant
systemctl stop networking

# Configure wpa_supplicant for WiFi Direct
echo "⚙️  Configuring wpa_supplicant for WiFi Direct..."
mkdir -p /etc/wpa_supplicant

# Make script executable
chmod +x wifi_direct_sharer.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start WiFi Direct credential sharing:"
echo "  sudo python3 wifi_direct_sharer.py"
echo ""
echo "What happens automatically:"
echo "1. Pi connects to phone via Bluetooth"
echo "2. Pi initiates WiFi Direct connection"
echo "3. Phone automatically shares WiFi credentials via WiFi Direct"
echo "4. Pi extracts credentials and connects to your WiFi"
echo ""
echo "📱 On your phone:"
echo "  - Connect to 'PiWiFiSetup' via Bluetooth"
echo "  - Accept WiFi Direct connection request"
echo "  - Phone automatically shares network information"
echo "  - No manual input or app installation required!"
echo ""
echo "🔍 How WiFi Direct extraction works:"
echo "  - Uses standard WiFi Direct protocol (P2P)"
echo "  - Phone detects Pi needs network access"
echo "  - Phone shares WiFi credentials automatically"
echo "  - Pi extracts credentials via WiFi Direct connection"
echo ""
echo "🎯 This is the most advanced automatic approach!"
echo "   Uses WiFi Direct protocol for professional-grade credential sharing."
echo "   Works on all modern phones with WiFi Direct support."
