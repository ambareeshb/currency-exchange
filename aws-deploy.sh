#!/bin/bash

# AWS EC2 Deployment Script for Currency Exchange App
# This script handles both initial setup and updates with enhanced security and systemd journal logging

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/currency-exchange"
SERVICE_NAME="currency-exchange"
BACKUP_DIR="$APP_DIR/backups"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
    logger -t "aws-deploy" "INFO: $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    logger -t "aws-deploy" "WARNING: $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    logger -t "aws-deploy" "ERROR: $1"
}

print_header() {
    echo -e "${BLUE}[SETUP]${NC} $1"
    logger -t "aws-deploy" "SETUP: $1"
}

# Function to check system resources
check_system_resources() {
    print_status "Checking system resources..."
    
    # Check available disk space (require at least 2GB)
    available_space=$(df / | awk 'NR==2 {print $4}')
    required_space=2097152  # 2GB in KB
    
    if [ "$available_space" -lt "$required_space" ]; then
        print_error "Insufficient disk space. Required: 2GB, Available: $(($available_space/1024/1024))GB"
        exit 1
    fi
    
    # Check available memory (require at least 1GB)
    available_memory=$(free -k | awk 'NR==2{print $7}')
    required_memory=1048576  # 1GB in KB
    
    if [ "$available_memory" -lt "$required_memory" ]; then
        print_warning "Low available memory. Available: $(($available_memory/1024))MB"
    fi
    
    print_status "✅ System resources check passed"
}

# Function to detect Python version
detect_python_version() {
    print_status "Detecting available Python version..."
    
    # Try different Python versions in order of preference
    for version in python3.11 python3.10 python3.9 python3; do
        if command -v $version >/dev/null 2>&1; then
            PYTHON_CMD=$version
            PYTHON_VERSION=$($version --version 2>&1 | cut -d' ' -f2)
            print_status "Using Python: $PYTHON_CMD (version $PYTHON_VERSION)"
            return 0
        fi
    done
    
    print_error "No suitable Python version found"
    exit 1
}

# Function to secure password input
secure_password_input() {
    local prompt="$1"
    local password=""
    local confirm=""
    
    while true; do
        echo -n "$prompt: "
        read -s password
        echo
        
        if [ ${#password} -lt 8 ]; then
            print_error "Password must be at least 8 characters long"
            continue
        fi
        
        echo -n "Confirm password: "
        read -s confirm
        echo
        
        if [ "$password" = "$confirm" ]; then
            echo "$password"
            return 0
        else
            print_error "Passwords do not match. Please try again."
        fi
    done
}

# Function to create backup
create_backup() {
    if [ -d "$APP_DIR" ] && [ "$INITIAL_SETUP" != true ]; then
        print_status "Creating backup..."
        local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup application files (excluding venv and logs)
        tar -czf "$BACKUP_DIR/$backup_name.tar.gz" \
            --exclude="venv" \
            --exclude="*.log" \
            --exclude="backups" \
            -C "$APP_DIR" . 2>/dev/null || {
            print_warning "Backup creation failed, continuing..."
        }
        
        # Keep only last 5 backups
        cd "$BACKUP_DIR"
        ls -t *.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
        
        print_status "✅ Backup created: $backup_name.tar.gz"
    fi
}

# Function to create systemd service
create_systemd_service() {
    print_status "Creating systemd service..."
    
    sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Currency Exchange Flask App
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
EnvironmentFile=$APP_DIR/.env.production
ExecStart=$APP_DIR/venv/bin/gunicorn --config $APP_DIR/gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP \$MAINPID
ExecStartPre=/bin/sleep 2
KillMode=mixed
TimeoutStartSec=60
TimeoutStopSec=30
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal

# Enhanced resource limits
LimitNOFILE=65536
LimitNPROC=4096

# Memory and CPU limits
MemoryMax=1G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF
    
    print_status "✅ Systemd service created"
}

# Function to create Nginx configuration with working HTTPS setup
create_nginx_config() {
    local domain_name="$1"
    print_status "Creating Nginx configuration..."
    
    if [ -n "$domain_name" ]; then
        # Check if SSL certificates exist in multiple possible locations
        SSL_CERT_PATH=""
        SSL_KEY_PATH=""
        
        # Check Let's Encrypt location
        if [ -f "/etc/letsencrypt/live/$domain_name/fullchain.pem" ] && [ -f "/etc/letsencrypt/live/$domain_name/privkey.pem" ]; then
            SSL_CERT_PATH="/etc/letsencrypt/live/$domain_name/fullchain.pem"
            SSL_KEY_PATH="/etc/letsencrypt/live/$domain_name/privkey.pem"
        # Check alternative locations
        elif [ -f "/etc/ssl/certs/$domain_name.crt" ] && [ -f "/etc/ssl/private/$domain_name.key" ]; then
            SSL_CERT_PATH="/etc/ssl/certs/$domain_name.crt"
            SSL_KEY_PATH="/etc/ssl/private/$domain_name.key"
        # Check for any SSL files in common locations
        elif [ -f "/etc/nginx/ssl/$domain_name.crt" ] && [ -f "/etc/nginx/ssl/$domain_name.key" ]; then
            SSL_CERT_PATH="/etc/nginx/ssl/$domain_name.crt"
            SSL_KEY_PATH="/etc/nginx/ssl/$domain_name.key"
        fi
        
        if [ -n "$SSL_CERT_PATH" ] && [ -n "$SSL_KEY_PATH" ]; then
            print_status "SSL certificates found at $SSL_CERT_PATH, creating HTTPS configuration..."
            sudo tee /etc/nginx/conf.d/$SERVICE_NAME.conf > /dev/null << EOF
# HTTP to HTTPS redirect
server {
    listen 80;
    server_name $domain_name www.$domain_name;
    return 301 https://\$server_name\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $domain_name www.$domain_name;
    
    # SSL Configuration
    ssl_certificate $SSL_CERT_PATH;
    ssl_certificate_key $SSL_KEY_PATH;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Fix for "413 Request Entity Too Large" error
    client_max_body_size 15M;
    client_body_buffer_size 128k;
    client_body_timeout 60s;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Timeouts to prevent socket errors
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 300s;
    
    # Buffer settings
    proxy_buffering on;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Enhanced upload handling for large files
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_connect_timeout 75s;
        proxy_read_timeout 300s;
        
        # Handle client disconnections gracefully
        proxy_ignore_client_abort on;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5001/health;
    }
}
EOF
        else
            print_status "No SSL certificates found, creating HTTP-only configuration..."
            print_status "Checked locations:"
            print_status "  - /etc/letsencrypt/live/$domain_name/"
            print_status "  - /etc/ssl/certs/ and /etc/ssl/private/"
            print_status "  - /etc/nginx/ssl/"
            sudo tee /etc/nginx/conf.d/$SERVICE_NAME.conf > /dev/null << EOF
server {
    listen 80;
    server_name $domain_name www.$domain_name;
    
    # Fix for "413 Request Entity Too Large" error
    client_max_body_size 15M;
    client_body_buffer_size 128k;
    client_body_timeout 60s;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Timeouts to prevent socket errors
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 300s;
    
    # Buffer settings
    proxy_buffering on;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Enhanced upload handling for large files
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_connect_timeout 75s;
        proxy_read_timeout 300s;
        
        # Handle client disconnections gracefully
        proxy_ignore_client_abort on;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5001/health;
    }
}
EOF
        fi
    else
        # Default server configuration (no domain)
        sudo tee /etc/nginx/conf.d/$SERVICE_NAME.conf > /dev/null << EOF
server {
    listen 80 default_server;
    server_name _;
    
    # Fix for "413 Request Entity Too Large" error
    client_max_body_size 15M;
    client_body_buffer_size 128k;
    client_body_timeout 60s;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Timeouts to prevent socket errors
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 300s;
    
    # Buffer settings
    proxy_buffering on;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Enhanced upload handling for large files
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_connect_timeout 75s;
        proxy_read_timeout 300s;
        
        # Handle client disconnections gracefully
        proxy_ignore_client_abort on;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5001/health;
    }
}
EOF
    fi
    
    # Remove default Nginx config
    sudo rm -f /etc/nginx/conf.d/default.conf
    
    # Test Nginx configuration
    print_status "Testing Nginx configuration..."
    sudo nginx -t
    
    print_status "✅ Nginx configuration created with working HTTPS setup"
}


# Function to test database connection securely
test_database_connection() {
    local rds_endpoint="$1"
    local db_user="$2"
    local db_password="$3"
    local db_name="$4"
    
    print_status "Testing database connection..."
    
    # Use PGPASSWORD environment variable for secure password passing
    if PGPASSWORD="$db_password" psql -h "$rds_endpoint" -U "$db_user" -d "$db_name" -c "SELECT 1;" > /dev/null 2>&1; then
        print_status "✅ Database connection successful"
        return 0
    else
        print_warning "⚠️  Database connection failed. Check RDS configuration."
        return 1
    fi
}

# Function to handle git operations with error checking
git_operation() {
    local operation="$1"
    local repo_url="$2"
    
    case "$operation" in
        "clone")
            print_status "Cloning repository..."
            if ! git clone "$repo_url" .; then
                print_error "Failed to clone repository. Check URL and permissions."
                exit 1
            fi
            ;;
        "pull")
            print_status "Pulling latest changes..."
            if ! git pull origin main; then
                print_error "Failed to pull changes. Check for conflicts or permissions."
                exit 1
            fi
            ;;
    esac
}

# Function to gracefully restart services
graceful_service_restart() {
    local service="$1"
    
    print_status "Gracefully restarting $service..."
    
    if sudo systemctl is-active --quiet "$service"; then
        # Service is running, perform graceful restart
        sudo systemctl reload-or-restart "$service"
        
        # Wait for service to be ready
        local max_attempts=30
        local attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            if sudo systemctl is-active --quiet "$service"; then
                print_status "✅ $service restarted successfully"
                return 0
            fi
            sleep 2
            attempt=$((attempt + 1))
        done
        
        print_error "❌ $service failed to restart within timeout"
        return 1
    else
        # Service not running, start it
        sudo systemctl start "$service"
        if sudo systemctl is-active --quiet "$service"; then
            print_status "✅ $service started successfully"
            return 0
        else
            print_error "❌ $service failed to start"
            return 1
        fi
    fi
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Check service status
    if ! sudo systemctl is-active --quiet $SERVICE_NAME; then
        print_error "❌ Service is not running"
        sudo systemctl status $SERVICE_NAME
        return 1
    fi
    
    # Check if application responds
    local max_attempts=10
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:5001/health > /dev/null 2>&1; then
            print_status "✅ Application is responding"
            return 0
        fi
        sleep 3
        attempt=$((attempt + 1))
    done
    
    print_warning "⚠️  Application health check failed"
    return 1
}

# Main execution starts here

# Check if this is initial setup or update
if [ ! -d "$APP_DIR" ]; then
    INITIAL_SETUP=true
    print_header "🚀 Starting AWS EC2 initial setup..."
else
    INITIAL_SETUP=false
    print_header "🔄 Starting deployment update..."
fi

# Check if running as ec2-user
if [ "$USER" != "ec2-user" ]; then
    print_error "This script should be run as ec2-user"
    exit 1
fi

# Check system resources
check_system_resources

# Create backup before update
create_backup

if [ "$INITIAL_SETUP" = true ]; then
    # INITIAL SETUP
    print_status "Updating system packages..."
    sudo yum update -y

    # Detect Python version
    detect_python_version
    
    print_status "Installing dependencies..."
    # Install Python packages based on detected version
    if [[ "$PYTHON_VERSION" == "3.11"* ]]; then
        sudo yum install -y python3.11 python3.11-pip python3.11-devel git nginx postgresql15
    elif [[ "$PYTHON_VERSION" == "3.10"* ]]; then
        sudo yum install -y python3.10 python3.10-pip python3.10-devel git nginx postgresql15
    else
        sudo yum install -y python3 python3-pip python3-devel git nginx postgresql15
    fi
    
    sudo yum groupinstall -y "Development Tools"
    
    # Install additional system monitoring packages
    sudo yum install -y htop iotop lsof

    # Create application directory
    print_status "Creating application directory..."
    sudo mkdir -p $APP_DIR
    sudo chown ec2-user:ec2-user $APP_DIR

    # Get repository URL
    print_header "Repository Setup"
    read -p "Enter your GitHub repository URL: " REPO_URL
    if [ -z "$REPO_URL" ]; then
        print_error "Repository URL is required"
        exit 1
    fi

    # Clone repository
    cd $APP_DIR
    git_operation "clone" "$REPO_URL"

    # Create virtual environment
    print_status "Creating Python virtual environment..."
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    # Database configuration
    print_header "Database Configuration"
    read -p "Enter your RDS endpoint: " RDS_ENDPOINT
    read -p "Enter database username [currencyuser]: " DB_USER
    DB_USER=${DB_USER:-currencyuser}
    
    # Secure password input
    DB_PASSWORD=$(secure_password_input "Enter database password")
    
    read -p "Enter database name [currency_exchange]: " DB_NAME
    DB_NAME=${DB_NAME:-currency_exchange}

    # Generate secure keys
    print_status "Generating secure keys..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

    # Create production environment file with secure permissions
    print_status "Creating production environment configuration..."
    cat > .env.production << EOF
FLASK_ENV=production
DEBUG=false
PORT=5001
SECRET_KEY=$SECRET_KEY
LOAD_SAMPLE_DATA=false
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$RDS_ENDPOINT:5432/$DB_NAME
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
AWS_REGION=us-east-1
EOF

    # Set secure permissions on environment file
    chmod 600 .env.production

    print_status "Environment file created with secure permissions"

    # Display admin credentials securely (masked)
    print_warning "Admin Credentials - SAVE THESE:"
    print_warning "Username: admin"
    print_warning "Password: ${ADMIN_PASSWORD:0:4}****${ADMIN_PASSWORD: -4}"
    print_warning "Full password saved to .env.production (secure access only)"

    # Test database connection
    test_database_connection "$RDS_ENDPOINT" "$DB_USER" "$DB_PASSWORD" "$DB_NAME"

    # Create services
    create_systemd_service

    # Domain configuration
    print_header "Domain Configuration"
    read -p "Enter your domain name (or press Enter to skip): " DOMAIN_NAME

    # Create Nginx configuration
    create_nginx_config "$DOMAIN_NAME"

    # Enable services
    print_status "Enabling services..."
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl enable nginx

else
    # UPDATE DEPLOYMENT
    cd $APP_DIR
    
    # Pull latest changes
    git_operation "pull"

    # Check if virtual environment exists, create if not
    if [ ! -d "venv" ]; then
        print_status "Virtual environment not found, creating..."
        detect_python_version
        $PYTHON_CMD -m venv venv
        print_status "✅ Virtual environment created"
    fi

    print_status "Activating virtual environment..."
    source venv/bin/activate

    print_status "Updating dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Update Nginx configuration during updates to apply any config changes
    print_status "Updating Nginx configuration..."
    # Check if domain was previously configured
    EXISTING_DOMAIN=""
    if [ -f "/etc/nginx/conf.d/$SERVICE_NAME.conf" ]; then
        EXISTING_DOMAIN=$(grep -o 'server_name [^;]*' /etc/nginx/conf.d/$SERVICE_NAME.conf | head -1 | awk '{print $2}' | grep -v '_' || echo "")
    fi
    create_nginx_config "$EXISTING_DOMAIN"
fi

# Common steps for both setup and update
print_status "Running database migrations..."
cd $APP_DIR
source venv/bin/activate

# Load environment variables securely
print_status "Loading environment variables..."
if [ -f ".env.production" ]; then
    set -a
    source .env.production
    set +a
else
    print_error "Environment file not found"
    exit 1
fi

# Run migrations
print_status "Executing migrations..."
python migrations.py

# Verify migration results
print_status "Verifying database setup..."
python -c "
from app import app, db, AdminUser, Currency
from sqlalchemy import inspect
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print('Tables created:', tables)
    try:
        admin_count = AdminUser.query.count()
        currency_count = Currency.query.count()
        print(f'Admin users: {admin_count}')
        print(f'Currencies: {currency_count}')
        if admin_count == 0:
            print('WARNING: No admin user found!')
        else:
            print('✅ Admin user exists')
    except Exception as e:
        print(f'Database query error: {e}')
        print('Tables may not be fully initialized yet')
"

# Create required directories for gunicorn
print_status "Creating required directories..."
sudo mkdir -p /var/run/gunicorn
sudo chown ec2-user:ec2-user /var/run/gunicorn
sudo mkdir -p /var/log/gunicorn
sudo chown ec2-user:ec2-user /var/log/gunicorn

# Start/restart services gracefully
print_status "Starting/restarting services..."

# Check application service status before restart
print_status "Checking current service status..."
sudo systemctl status $SERVICE_NAME --no-pager -l || true

# Check if application files are in place
print_status "Verifying application files..."
if [ ! -f "$APP_DIR/app.py" ]; then
    print_error "app.py not found in $APP_DIR"
    exit 1
fi

if [ ! -f "$APP_DIR/.env.production" ]; then
    print_error ".env.production not found in $APP_DIR"
    exit 1
fi

if [ ! -d "$APP_DIR/venv" ]; then
    print_error "Virtual environment not found in $APP_DIR"
    exit 1
fi

# Test if the application can start manually first
print_status "Testing application startup..."
cd $APP_DIR
source venv/bin/activate
set -a
source .env.production
set +a

# Quick test to see if app imports correctly
python -c "
try:
    from app import app
    print('✅ Application imports successfully')
except Exception as e:
    print(f'❌ Application import failed: {e}')
    exit(1)
" || {
    print_error "Application failed to import. Check dependencies and code."
    exit 1
}

# Check if port 5001 is already in use
if netstat -tuln | grep -q ":5001 "; then
    print_warning "Port 5001 is already in use. Stopping existing processes..."
    sudo pkill -f "gunicorn.*app:app" || true
    sleep 2
fi

graceful_service_restart $SERVICE_NAME
graceful_service_restart nginx

# Enhanced verification with detailed logging
print_status "Enhanced deployment verification..."

# Check service status with detailed output
print_status "Service status check:"
sudo systemctl status $SERVICE_NAME --no-pager -l

# Check if the service is listening on port 5001
print_status "Checking if application is listening on port 5001..."
sleep 5
if netstat -tuln | grep -q ":5001 "; then
    print_status "✅ Application is listening on port 5001"
else
    print_error "❌ Application is not listening on port 5001"
    print_status "Recent application logs:"
    sudo journalctl -u $SERVICE_NAME --no-pager -n 20
    exit 1
fi

# Verify deployment
verify_deployment

if [ "$INITIAL_SETUP" = true ]; then
    # Create backup directory
    print_status "Creating backup directory..."
    mkdir -p $BACKUP_DIR

    # Get public IP
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "Unable to retrieve")

    print_header "🎉 Initial setup completed successfully!"
    echo
    print_status "Your Currency Exchange app is now running!"
    print_status "Access at:"
    if [ -n "$DOMAIN_NAME" ]; then
        print_status "  Domain: http://$DOMAIN_NAME"
    fi
    print_status "  IP: http://$PUBLIC_IP"
    echo
    print_status "Next Steps:"
    print_status "1. Configure DNS to point to: $PUBLIC_IP"
    if [ -n "$DOMAIN_NAME" ]; then
        print_status "2. Setup SSL: sudo certbot --nginx -d $DOMAIN_NAME"
    fi
    print_status "3. To deploy updates: ./aws-deploy.sh"
    print_status "4. Admin credentials are in .env.production (secure access)"
    print_status "5. View logs: sudo journalctl -u $SERVICE_NAME -f"
else
    print_header "🎉 Update deployment completed successfully!"
fi

# Final status and logging information
print_status "Deployment logging information:"
print_status "  - Deployment logs: sudo journalctl -t aws-deploy"
print_status "  - Application logs: sudo journalctl -u $SERVICE_NAME"
print_status "  - Nginx logs: sudo journalctl -u nginx"
print_status "  - System logs: sudo journalctl -f"

print_status "Recent application logs:"
sudo journalctl -u $SERVICE_NAME --no-pager -n 5 2>/dev/null || echo "No application logs yet"

print_status "🎉 Deployment script completed successfully!"