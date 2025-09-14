#!/bin/bash

# Fix log directories for Currency Exchange service
# This script ensures all required log directories exist and have proper permissions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
APP_DIR="/opt/currency-exchange"
SERVICE_NAME="currency-exchange"

print_status "🔧 Fixing log directories for Currency Exchange service..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root or with sudo"
    exit 1
fi

# Create log directories
print_status "Creating log directories..."
mkdir -p /var/log/gunicorn
mkdir -p /var/log/currency-exchange
mkdir -p /var/run/gunicorn

# Set proper ownership
print_status "Setting proper ownership..."
chown ec2-user:ec2-user /var/log/gunicorn
chown ec2-user:ec2-user /var/log/currency-exchange
chown ec2-user:ec2-user /var/run/gunicorn

# Create log files if they don't exist
print_status "Creating log files..."
touch /var/log/gunicorn/access.log
touch /var/log/gunicorn/error.log
touch /var/log/currency-exchange/app.log

# Set proper permissions on log files
chown ec2-user:ec2-user /var/log/gunicorn/access.log
chown ec2-user:ec2-user /var/log/gunicorn/error.log
chown ec2-user:ec2-user /var/log/currency-exchange/app.log

chmod 644 /var/log/gunicorn/access.log
chmod 644 /var/log/gunicorn/error.log
chmod 644 /var/log/currency-exchange/app.log

# Set proper directory permissions
chmod 755 /var/log/gunicorn
chmod 755 /var/log/currency-exchange
chmod 755 /var/run/gunicorn

print_status "✅ Log directories and files created successfully"

# Verify the setup
print_status "Verifying log directory setup..."
if [ -d "/var/log/gunicorn" ] && [ -w "/var/log/gunicorn" ]; then
    print_status "✅ /var/log/gunicorn exists and is writable"
else
    print_error "❌ /var/log/gunicorn is not accessible"
    exit 1
fi

if [ -f "/var/log/gunicorn/error.log" ] && [ -w "/var/log/gunicorn/error.log" ]; then
    print_status "✅ /var/log/gunicorn/error.log exists and is writable"
else
    print_error "❌ /var/log/gunicorn/error.log is not accessible"
    exit 1
fi

# Check if service exists and restart it
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    print_status "Restarting ${SERVICE_NAME} service..."
    systemctl stop ${SERVICE_NAME} || true
    sleep 2
    systemctl start ${SERVICE_NAME}
    
    # Check if service started successfully
    sleep 3
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        print_status "✅ ${SERVICE_NAME} service restarted successfully"
    else
        print_warning "⚠️  Service may have issues. Checking status..."
        systemctl status ${SERVICE_NAME} --no-pager -l
    fi
else
    print_warning "⚠️  ${SERVICE_NAME} service not found. Log directories are ready for when service is created."
fi

print_status "🎉 Log directory fix completed!"
print_status "You can now check the service status with: sudo systemctl status ${SERVICE_NAME}"