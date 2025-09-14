#!/bin/bash

# AWS EC2 Deployment Script for Currency Exchange App
# This script handles both initial setup and updates

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

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

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

if [ "$INITIAL_SETUP" = true ]; then
    # INITIAL SETUP
    print_status "Updating system packages..."
    sudo yum update -y

    print_status "Installing dependencies..."
    sudo yum install -y python3.11 python3.11-pip python3.11-devel git nginx postgresql15
    sudo yum groupinstall -y "Development Tools"
    
    # Install additional packages for socket recovery
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
    print_status "Cloning repository..."
    cd $APP_DIR
    git clone $REPO_URL .

    # Create virtual environment
    print_status "Creating Python virtual environment..."
    python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Install additional Python packages for socket recovery
    pip install psutil

    # Database configuration
    print_header "Database Configuration"
    read -p "Enter your RDS endpoint: " RDS_ENDPOINT
    read -p "Enter database username [currencyuser]: " DB_USER
    DB_USER=${DB_USER:-currencyuser}
    read -s -p "Enter database password: " DB_PASSWORD
    echo
    read -p "Enter database name [currency_exchange]: " DB_NAME
    DB_NAME=${DB_NAME:-currency_exchange}

    # Generate secure keys
    print_status "Generating secure keys..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

    # Create production environment file (not committed to GitHub)
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

    print_status "Environment file created. Contents:"
    cat .env.production

    print_warning "Admin Credentials - SAVE THESE:"
    print_warning "Username: admin"
    print_warning "Password: $ADMIN_PASSWORD"

    # Test database connection
    print_status "Testing database connection..."
    if psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME -c "SELECT 1;" > /dev/null 2>&1; then
        print_status "✅ Database connection successful"
    else
        print_warning "⚠️  Database connection failed. Check RDS configuration."
    fi

    # Create log directories with enhanced structure
    print_status "Creating log directories..."
    sudo mkdir -p /var/log/gunicorn /var/log/currency-exchange /var/run/gunicorn
    sudo chown ec2-user:ec2-user /var/log/gunicorn /var/log/currency-exchange /var/run/gunicorn
    
    # Set up log rotation to prevent disk space issues
    sudo tee /etc/logrotate.d/currency-exchange > /dev/null << 'EOF'
/var/log/currency-exchange/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ec2-user ec2-user
    postrotate
        systemctl reload currency-exchange || true
    endscript
}

/var/log/gunicorn/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ec2-user ec2-user
    postrotate
        systemctl reload currency-exchange || true
    endscript
}
EOF

    # Create enhanced systemd service with socket error recovery
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

# Enhanced resource limits to prevent socket issues
LimitNOFILE=65536
LimitNPROC=4096

# Memory and CPU limits
MemoryMax=1G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF

    # Create socket recovery service
    print_status "Creating socket recovery service..."
    sudo tee /etc/systemd/system/currency-exchange-recovery.service > /dev/null << EOF
[Unit]
Description=Currency Exchange Socket Recovery Service
After=currency-exchange.service
Requires=currency-exchange.service

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/socket_recovery.py --daemon
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Create socket recovery timer for regular checks
    sudo tee /etc/systemd/system/currency-exchange-recovery.timer > /dev/null << EOF
[Unit]
Description=Currency Exchange Socket Recovery Timer
Requires=currency-exchange-recovery.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=2min
Unit=currency-exchange-recovery.service

[Install]
WantedBy=timers.target
EOF

    # Domain configuration
    print_header "Domain Configuration"
    read -p "Enter your domain name (or press Enter to skip): " DOMAIN_NAME

    # Create Nginx configuration with improved settings
    print_status "Creating Nginx configuration..."
    if [ -n "$DOMAIN_NAME" ]; then
        sudo tee /etc/nginx/conf.d/$SERVICE_NAME.conf > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Timeouts to prevent socket errors
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
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
        sudo tee /etc/nginx/conf.d/$SERVICE_NAME.conf > /dev/null << EOF
server {
    listen 80 default_server;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Timeouts to prevent socket errors
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
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

    # Enable services including recovery mechanisms
    print_status "Enabling services..."
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl enable currency-exchange-recovery
    sudo systemctl enable currency-exchange-recovery.timer
    sudo systemctl enable nginx
    
    # Make scripts executable
    chmod +x $APP_DIR/monitor.sh
    chmod +x $APP_DIR/socket_recovery.py

else
    # UPDATE DEPLOYMENT
    cd $APP_DIR
    print_status "Pulling latest changes..."
    git pull origin main

    print_status "Activating virtual environment..."
    source venv/bin/activate

    print_status "Updating dependencies..."
    pip install -r requirements.txt
fi

# Common steps for both setup and update
print_status "Running database migrations..."
cd $APP_DIR
source venv/bin/activate

# Load environment variables for migrations
print_status "Loading environment variables..."
export $(cat .env.production | grep -v '^#' | xargs)

# Run migrations with environment loaded
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

print_status "Starting/restarting services..."
sudo systemctl start $SERVICE_NAME
sudo systemctl start currency-exchange-recovery
sudo systemctl start currency-exchange-recovery.timer
sudo systemctl start nginx

# Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    print_status "✅ Currency Exchange service is running"
else
    print_error "❌ Service failed to start"
    sudo systemctl status $SERVICE_NAME
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    print_status "✅ Nginx is running"
else
    print_error "❌ Nginx failed to start"
    sudo systemctl status nginx
    exit 1
fi

# Check recovery service status
if sudo systemctl is-active --quiet currency-exchange-recovery; then
    print_status "✅ Socket recovery service is running"
else
    print_warning "⚠️  Socket recovery service not running (this is optional)"
fi

if [ "$INITIAL_SETUP" = true ]; then
    # Create backup directory
    print_status "Creating backup directory..."
    mkdir -p $APP_DIR/backups

    # Get public IP
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

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
else
    print_header "🎉 Update deployment completed successfully!"
fi

print_status "Recent logs:"
sudo journalctl -u $SERVICE_NAME --no-pager -n 5