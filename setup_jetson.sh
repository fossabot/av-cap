#!/bin/bash
# Jetson Camera Capture Setup Script
# This script installs and configures the multi-camera capture system on Jetson devices

set -e  # Exit on any error

# Default values
CREATE_SYSTEMD_SERVICE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --create-service)
            CREATE_SYSTEMD_SERVICE=true
            shift
            ;;
        --no-service)
            CREATE_SYSTEMD_SERVICE=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --create-service    Create systemd service for auto-startup"
            echo "  --no-service        Skip creating systemd service (default)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo "=== Jetson Camera Capture Setup ==="
echo "This script will install dependencies and configure the Jetson for multi-camera capture."
echo ""

# Check if running on Jetson
if ! grep -q "jetson" /etc/hostname 2>/dev/null && ! grep -q "nvidia" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Jetson devices. Continue anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-opencv \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    v4l-utils \
    v4l2loopback-dkms \
    libv4l-dev

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Add user to video group for camera access
echo "Configuring camera permissions..."
if ! groups $USER | grep -q video; then
    sudo usermod -a -G video $USER
    echo "Added user to video group. You may need to log out and back in for changes to take effect."
else
    echo "User already in video group."
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p frames
mkdir -p test_frames
mkdir -p logs

# Set up log rotation
echo "Setting up log rotation..."
sudo tee /etc/logrotate.d/camera-capture > /dev/null <<EOF
/path/to/project/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 644 $USER $USER
}
EOF

# Create a systemd service for automatic startup (optional)
if [ "$CREATE_SYSTEMD_SERVICE" = true ]; then
    echo "Creating systemd service for auto-startup..."
    sudo tee /etc/systemd/system/camera-capture.service > /dev/null <<EOF
[Unit]
Description=Multi-Camera Capture Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/camera_capture.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    # Enable the service
    sudo systemctl daemon-reload
    sudo systemctl enable camera-capture.service
    echo "✓ Systemd service created and enabled"
    echo "  To start the service: sudo systemctl start camera-capture"
    echo "  To stop the service: sudo systemctl stop camera-capture"
    echo "  To check status: sudo systemctl status camera-capture"
else
    echo "Skipping systemd service creation (use --create-service to enable)"
fi

# Make scripts executable
echo "Making scripts executable..."
chmod +x camera_capture.py
chmod +x camera_test.py

# Test camera detection
echo "Testing camera detection..."
echo "Available video devices:"
ls -la /dev/video* 2>/dev/null || echo "No video devices found"

# Check V4L2 capabilities
if command -v v4l2-ctl &> /dev/null; then
    echo "V4L2 utilities available."
    echo "To list camera capabilities, run: v4l2-ctl --list-devices"
else
    echo "V4L2 utilities not found. Installing..."
    sudo apt-get install -y v4l-utils
fi

# Create a simple test script
echo "Creating quick test script..."
cat > quick_test.sh <<'EOF'
#!/bin/bash
echo "Quick camera test..."
python3 camera_test.py --scan
echo ""
echo "To test specific cameras, run:"
echo "python3 camera_test.py --test 0 1 2"
EOF
chmod +x quick_test.sh

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Log out and back in (or reboot) for video group permissions to take effect"
echo "2. Test cameras: ./quick_test.sh"
echo "3. Start capturing: python3 camera_capture.py"
echo ""
if [ "$CREATE_SYSTEMD_SERVICE" = true ]; then
    echo "Systemd service is enabled and will start automatically on boot"
    echo "To manually control the service:"
    echo "  Start: sudo systemctl start camera-capture"
    echo "  Stop: sudo systemctl stop camera-capture"
    echo "  Status: sudo systemctl status camera-capture"
    echo ""
fi
echo "Useful commands:"
echo "- Test cameras: python3 camera_test.py --scan"
echo "- Capture from cameras 0,1,2: python3 camera_capture.py --cameras 0 1 2"
echo "- Capture for 60 seconds: python3 camera_capture.py --duration 60"
echo "- View camera info: v4l2-ctl --list-devices"
echo ""
echo "For troubleshooting, see README.md" 