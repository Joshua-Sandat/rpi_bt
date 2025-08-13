# Android WiFi Direct Credential Sharer for Raspberry Pi Zero 2 W

## 🎯 **What This Does**

Automatically extracts WiFi credentials from **Android phones** using WiFi Direct (P2P) protocol. No phone app installation required - just connect via Bluetooth and the Pi will automatically request and receive WiFi credentials.

## 🚀 **How It Works (Android-Specific)**

1. **Pi creates Bluetooth service** named "PiWiFiSetup"
2. **Android phone connects** to Pi via Bluetooth
3. **Pi initiates WiFi Direct connection** to the Android phone
4. **Android shows WiFi Direct prompt** (this is the key difference from iOS!)
5. **Android automatically shares** WiFi credentials via WiFi Direct
6. **Pi extracts credentials** and connects to your home WiFi network

## ✅ **Why This Works Better with Android**

- **Android actively supports WiFi Direct** and shows connection prompts
- **Android automatically shares WiFi credentials** when requested
- **No manual intervention** required on the Android phone
- **Professional product experience** - just like commercial WiFi sharing devices

## 📱 **Android Phone Requirements**

- **Android 4.0+** (API level 14+)
- **WiFi Direct capability** (most modern Android phones have this)
- **Bluetooth enabled**
- **WiFi enabled** (to share current network credentials)

## 🛠️ **Setup Instructions**

### **Step 1: Run Setup Script**
```bash
# Make script executable
chmod +x setup_android_wifi_direct.sh

# Run setup (must be root)
sudo ./setup_android_wifi_direct.sh
```

### **Step 2: Start the Service**
```bash
# Start the service
sudo systemctl start android-wifi-direct-sharer

# Check status
sudo systemctl status android-wifi-direct-sharer

# View logs
sudo journalctl -u android-wifi-direct-sharer -f
```

### **Step 3: Connect Android Phone**
1. **On your Android phone:**
   - Go to **Bluetooth settings**
   - Look for **"PiWiFiSetup"**
   - **Connect** to it

2. **Pi will automatically:**
   - Detect the Android connection
   - Initiate WiFi Direct connection
   - Request WiFi credentials
   - Connect to your home network

## 🔧 **Manual Testing**

If you want to test manually instead of using the service:

```bash
# Run the script directly
sudo python3 android_wifi_direct_sharer.py

# Check WiFi Direct status
sudo wpa_cli status

# Check discovered devices
sudo wpa_cli p2p_peers

# Check WiFi connection
iwconfig wlan0
```

## 📊 **Troubleshooting**

### **No WiFi Direct Prompt on Android**
- **Check Android WiFi Direct settings** - some phones have this disabled
- **Ensure WiFi is enabled** on the Android phone
- **Try reconnecting** Bluetooth connection
- **Check logs**: `sudo journalctl -u android-wifi-direct-sharer -f`

### **WiFi Direct Discovery Fails**
- **Restart the service**: `sudo systemctl restart android-wifi-direct-sharer`
- **Check wpa_supplicant**: `sudo wpa_cli status`
- **Verify Bluetooth**: `bluetoothctl info`

### **Credentials Extracted But No Internet**
- **Check WiFi connection**: `iwconfig wlan0`
- **Verify network**: `ping 8.8.8.8`
- **Check wpa_supplicant logs**: `sudo wpa_cli status`

## 🗂️ **File Structure**

```
├── android_wifi_direct_sharer.py      # Main Python script
├── setup_android_wifi_direct.sh       # Setup script
├── README_Android_WiFi_Direct.md      # This file
└── /etc/wifi_credentials.json         # Extracted credentials (created automatically)
```

## 🔍 **Debugging Commands**

```bash
# Check WiFi Direct status
sudo wpa_cli p2p_peers
sudo wpa_cli p2p_group_info
sudo wpa_cli status

# Check Bluetooth status
bluetoothctl info
bluetoothctl devices

# Check network interfaces
ip addr show
iwconfig wlan0

# View service logs
sudo journalctl -u android-wifi-direct-sharer -f
```

## ⚡ **Performance Tips**

- **Android phones respond faster** than iOS devices
- **WiFi Direct discovery** typically takes 10-15 seconds
- **Connection establishment** takes 20-45 seconds
- **Total process** usually completes in 1-2 minutes

## 🚨 **Important Notes**

- **Must run as root** (sudo) due to network configuration
- **Stops existing WiFi services** during setup
- **Creates systemd service** for auto-start
- **Logs to both file and journal** for debugging
- **Automatically restarts** if it crashes

## 🔄 **Service Management**

```bash
# Start service
sudo systemctl start android-wifi-direct-sharer

# Stop service
sudo systemctl stop android-wifi-direct-sharer

# Restart service
sudo systemctl restart android-wifi-direct-sharer

# Enable auto-start
sudo systemctl enable android-wifi-direct-sharer

# Disable auto-start
sudo systemctl disable android-wifi-direct-sharer

# Check status
sudo systemctl status android-wifi-direct-sharer
```

## 🎉 **Success Indicators**

When working correctly, you should see:
1. **"Android device connected"** in logs
2. **WiFi Direct discovery** messages
3. **"Android WiFi Direct connection established"**
4. **"Android WiFi credentials extracted"**
5. **"Successfully connected to WiFi network"**
6. **Internet access** on your Pi

## 🆘 **Getting Help**

If you encounter issues:
1. **Check the logs**: `sudo journalctl -u android-wifi-direct-sharer -f`
2. **Verify Android WiFi Direct** is enabled on your phone
3. **Ensure WiFi is enabled** on the Android phone
4. **Try reconnecting** the Bluetooth connection
5. **Restart the service**: `sudo systemctl restart android-wifi-direct-sharer`

---

**🎯 This system is specifically optimized for Android devices and should provide a much more reliable experience than the generic WiFi Direct approach!**
