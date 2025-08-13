#!/bin/bash
# Android WiFi Direct Credential Sharer Setup Script
# Optimized for Raspberry Pi Zero 2 W and Android devices

set -e

echo "🚀 Setting up Android WiFi Direct Credential Sharer..."
echo "This script will configure your Pi for Android WiFi Direct credential extraction"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Update package list
echo "📦 Updating package list..."
apt update

# Install required packages
echo "📦 Installing required packages..."
apt install -y \
    bluez \
    bluez-tools \
    wpasupplicant \
    python3-dbus \
    python3-gi \
    python3-pip \
    network-manager

# Stop conflicting services
echo "🛑 Stopping conflicting services..."
systemctl stop wpa_supplicant 2>/dev/null || true
systemctl stop networking 2>/dev/null || true
systemctl stop bluetooth 2>/dev/null || true

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p /etc/wpa_supplicant
mkdir -p /var/log

# Configure Bluetooth for Android compatibility
echo "🔵 Configuring Bluetooth for Android..."
cat > /etc/bluetooth/main.conf << 'EOF'
[General]
Name = PiWiFiSetup
Class = 0x000100
DiscoverableTimeout = 0
PairableTimeout = 0
AutoEnable = true

[Policy]
AutoEnable = true
EOF

# Configure wpa_supplicant for Android WiFi Direct
echo "📶 Configuring wpa_supplicant for Android WiFi Direct..."
cat > /etc/wpa_supplicant/wpa_supplicant.conf << 'EOF'
ctrl_interface=/var/run/wpa_supplicant
ctrl_interface_group=0
update_config=1

# Minimal WiFi Direct configuration - compatible with all Pi versions
p2p_disabled=0
EOF

# Enable and start Bluetooth service
echo "🔵 Starting Bluetooth service..."
systemctl enable bluetooth
systemctl start bluetooth

# Wait for Bluetooth to be ready
sleep 3

# Make Pi discoverable and pairable
echo "🔵 Making Pi discoverable and pairable..."
bluetoothctl discoverable on
bluetoothctl pairable on

# Create systemd service for auto-start
echo "⚙️ Creating systemd service for auto-start..."
cat > /etc/systemd/system/android-wifi-direct-sharer.service << 'EOF'
[Unit]
Description=Android WiFi Direct Credential Sharer
After=bluetooth.service
Wants=bluetooth.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /home/gt/rpi_bt/android_wifi_direct_sharer.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable android-wifi-direct-sharer.service

# Set proper permissions
echo "🔐 Setting proper permissions..."
chmod +x /home/gt/rpi_bt/android_wifi_direct_sharer.py
chown root:root /home/gt/rpi_bt/android_wifi_direct_sharer.py

# Create log rotation
echo "📝 Setting up log rotation..."
cat > /etc/logrotate.d/android-wifi-direct-sharer << 'EOF'
/var/log/android_wifi_direct_sharer.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

# Test WiFi Direct functionality
echo "🧪 Testing WiFi Direct functionality..."
if command -v wpa_cli >/dev/null 2>&1; then
    echo "✅ wpa_cli is available"
else
    echo "❌ wpa_cli is not available"
    exit 1
fi

# Final configuration
echo "🎯 Final configuration..."
echo "PiWiFiSetup will appear in Bluetooth settings"
echo "Android devices can connect and share WiFi credentials"
echo ""

# Display status
echo "📊 Current status:"
echo "Bluetooth: $(systemctl is-active bluetooth)"
echo "Service: $(systemctl is-enabled android-wifi-direct-sharer.service)"
echo ""

echo "✅ Android WiFi Direct setup complete!"
echo ""
echo "🚀 To start the service:"
echo "   sudo systemctl start android-wifi-direct-sharer"
echo ""
echo "📱 On your Android phone:"
echo "   1. Go to Bluetooth settings"
echo "   2. Connect to 'PiWiFiSetup'"
echo "   3. Pi will attempt WiFi Direct credential extraction"
echo "   4. Android should show WiFi Direct connection prompt"
echo ""
echo "🔍 To view logs:"
echo "   sudo journalctl -u android-wifi-direct-sharer -f"
echo ""
echo "🔄 To restart the service:"
echo "   sudo systemctl restart android-wifi-direct-sharer"
echo ""
echo "🎉 Setup complete! Your Pi is ready for Android WiFi Direct credential sharing!"
