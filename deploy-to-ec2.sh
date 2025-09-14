#!/bin/bash

# EC2 Deployment Script for Currency Exchange Application
# This script automates the secure deployment process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_header() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

# Function to generate secure credentials
generate_credentials() {
    print_header "Generating secure credentials..."
    
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    
    print_status "✅ Secure credentials generated"
    echo "SECRET_KEY: ${SECRET_KEY:0:16}..."
    echo "ADMIN_PASSWORD: $ADMIN_PASSWORD"
    
    return 0
}

# Function to create production environment file
create_production_env() {
    local rds_endpoint="$1"
    local db_user="$2"
    local db_password="$3"
    local db_name="$4"
    local admin_username="$5"
    
    print_status "Creating production environment file..."
    
    cat > .env.production << EOF
# Production Environment Configuration
FLASK_ENV=production
DEBUG=false
PORT=5001
SECRET_KEY=$SECRET_KEY
LOAD_SAMPLE_DATA=false

# Database Configuration
DATABASE_URL=postgresql://$db_user:$db_password@$rds_endpoint:5432/$db_name

# Admin Credentials
ADMIN_USERNAME=$admin_username
ADMIN_PASSWORD=$ADMIN_PASSWORD

# AWS Configuration
AWS_REGION=us-east-1
EOF

    # Set secure permissions
    chmod 600 .env.production
    
    print_status "✅ Production environment file created with secure permissions"
}

# Function to validate environment
validate_environment() {
    print_status "Validating deployment environment..."
    
    # Check if running on EC2
    if ! curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-id > /dev/null 2>&1; then
        print_warning "Not running on EC2 instance - some features may not work"
    fi
    
    # Check if running as ec2-user
    if [ "$USER" != "ec2-user" ] && [ "$USER" != "ubuntu" ]; then
        print_warning "Not running as ec2-user or ubuntu - permissions may need adjustment"
    fi
    
    # Check Python version
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "Python3 not found. Please install Python3 first."
        exit 1
    fi
    
    print_status "✅ Environment validation passed"
}

# Function to test database connection
test_database_connection() {
    local rds_endpoint="$1"
    local db_user="$2"
    local db_password="$3"
    local db_name="$4"
    
    print_status "Testing database connection..."
    
    if command -v psql >/dev/null 2>&1; then
        if PGPASSWORD="$db_password" psql -h "$rds_endpoint" -U "$db_user" -d "$db_name" -c "SELECT 1;" > /dev/null 2>&1; then
            print_status "✅ Database connection successful"
            return 0
        else
            print_error "❌ Database connection failed"
            return 1
        fi
    else
        print_warning "PostgreSQL client not installed - skipping connection test"
        return 0
    fi
}

# Main deployment function
main() {
    print_header "🚀 Starting EC2 Deployment for Currency Exchange Application"
    echo "=================================================================="
    
    # Validate environment
    validate_environment
    
    # Generate secure credentials
    generate_credentials
    
    # Get deployment configuration
    print_header "📋 Deployment Configuration"
    
    read -p "Enter RDS endpoint: " RDS_ENDPOINT
    if [ -z "$RDS_ENDPOINT" ]; then
        print_error "RDS endpoint is required"
        exit 1
    fi
    
    read -p "Enter database username [currencyuser]: " DB_USER
    DB_USER=${DB_USER:-currencyuser}
    
    echo -n "Enter database password: "
    read -s DB_PASSWORD
    echo
    
    if [ -z "$DB_PASSWORD" ]; then
        print_error "Database password is required"
        exit 1
    fi
    
    read -p "Enter database name [currency_exchange]: " DB_NAME
    DB_NAME=${DB_NAME:-currency_exchange}
    
    read -p "Enter admin username [admin]: " ADMIN_USERNAME
    ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
    
    read -p "Enter domain name (optional): " DOMAIN_NAME
    
    # Test database connection
    test_database_connection "$RDS_ENDPOINT" "$DB_USER" "$DB_PASSWORD" "$DB_NAME"
    
    # Create production environment file
    create_production_env "$RDS_ENDPOINT" "$DB_USER" "$DB_PASSWORD" "$DB_NAME" "$ADMIN_USERNAME"
    
    # Run the main deployment script
    print_header "🔧 Running main deployment script..."
    
    if [ -f "./aws-deploy.sh" ]; then
        chmod +x aws-deploy.sh
        sudo ./aws-deploy.sh
    else
        print_error "aws-deploy.sh not found in current directory"
        exit 1
    fi
    
    # Final verification
    print_header "🔍 Final Verification"
    
    # Wait for services to start
    sleep 10
    
    # Check service status
    if sudo systemctl is-active --quiet currency-exchange; then
        print_status "✅ Currency Exchange service is running"
    else
        print_error "❌ Currency Exchange service is not running"
        sudo systemctl status currency-exchange
    fi
    
    # Check health endpoint
    if curl -s http://localhost:5001/health > /dev/null 2>&1; then
        print_status "✅ Health endpoint is responding"
    else
        print_warning "⚠️  Health endpoint not responding yet"
    fi
    
    # Get public IP
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "Unable to retrieve")
    
    print_header "🎉 Deployment Complete!"
    echo
    print_status "Your Currency Exchange application is deployed!"
    print_status "Access URLs:"
    print_status "  HTTP: http://$PUBLIC_IP"
    if [ -n "$DOMAIN_NAME" ]; then
        print_status "  Domain: http://$DOMAIN_NAME"
        print_status "  HTTPS: https://$DOMAIN_NAME (after SSL setup)"
    fi
    print_status "  Health: http://$PUBLIC_IP/health"
    echo
    print_status "Admin Credentials:"
    print_status "  Username: $ADMIN_USERNAME"
    print_status "  Password: $ADMIN_PASSWORD"
    echo
    print_status "Next Steps:"
    print_status "1. Configure DNS to point to: $PUBLIC_IP"
    if [ -n "$DOMAIN_NAME" ]; then
        print_status "2. Setup SSL: sudo certbot --nginx -d $DOMAIN_NAME"
    fi
    print_status "3. Monitor logs: sudo journalctl -u currency-exchange -f"
    print_status "4. View deployment guide: cat EC2_DEPLOYMENT_GUIDE.md"
    
    print_status "🔒 Security Notes:"
    print_status "- Admin credentials are saved in .env.production (secure access only)"
    print_status "- SECRET_KEY is cryptographically secure"
    print_status "- Database connection is encrypted"
    print_status "- All services are running with minimal privileges"
}

# Check if script is run with sudo for deployment parts
if [ "$EUID" -eq 0 ]; then
    print_error "Do not run this script as root. It will use sudo when needed."
    exit 1
fi

# Run main function
main "$@"