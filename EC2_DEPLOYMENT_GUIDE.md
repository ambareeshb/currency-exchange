# EC2 Production Deployment Guide

This guide provides step-by-step instructions for deploying the Currency Exchange application to AWS EC2 with all security improvements applied.

## 🚀 Quick Start

### Prerequisites
- AWS EC2 instance (Amazon Linux 2 or Ubuntu)
- SSH access to your EC2 instance
- Domain name (optional but recommended)
- RDS PostgreSQL instance (recommended for production)

### 1. Launch EC2 Instance

**Recommended Configuration:**
- **Instance Type:** t3.small or larger (t3.micro for testing)
- **AMI:** Amazon Linux 2 or Ubuntu 20.04 LTS
- **Storage:** 20GB GP3 SSD minimum
- **Security Group:** Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

**Security Group Rules:**
```
Type        Protocol    Port Range    Source
SSH         TCP         22           Your IP/0.0.0.0/0
HTTP        TCP         80           0.0.0.0/0
HTTPS       TCP         443          0.0.0.0/0
```

### 2. Connect to Your Instance

```bash
# Replace with your key file and instance IP
ssh -i your-key.pem ec2-user@your-ec2-public-ip
```

### 3. Upload Application Code

**Option A: From Git Repository**
```bash
# On EC2 instance
git clone https://github.com/your-username/currency-exchange.git
cd currency-exchange
```

**Option B: Upload from Local Machine**
```bash
# From your local machine
scp -i your-key.pem -r /path/to/currency-exchange ec2-user@your-ec2-ip:/home/ec2-user/
```

## 🔧 Automated Deployment

### Step 1: Prepare Environment Configuration

Before running the deployment script, you **MUST** update the environment file:

```bash
# Edit the AWS environment file
nano .env.aws
```

**Update these critical values:**

```bash
# Generate secure secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Set secure admin credentials
ADMIN_USERNAME=your_secure_admin_username
ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

# Configure your RDS database
DATABASE_URL=postgresql://username:password@your-rds-endpoint.region.rds.amazonaws.com:5432/currency_exchange

# Set your AWS region
AWS_REGION=us-east-1
```

### Step 2: Run Deployment Script

```bash
# Make script executable
chmod +x aws-deploy.sh

# Run deployment (will prompt for configuration)
sudo ./aws-deploy.sh
```

**The script will:**
1. Install system dependencies (Python, PostgreSQL, Nginx)
2. Create application directory (`/opt/currency-exchange`)
3. Set up Python virtual environment
4. Install application dependencies
5. Configure systemd service
6. Set up Nginx reverse proxy
7. Configure SSL (if domain provided)
8. Start all services

### Step 3: Deployment Script Prompts

During deployment, you'll be prompted for:

1. **Repository URL:** Your GitHub repository URL
2. **RDS Endpoint:** Your PostgreSQL RDS endpoint
3. **Database Username:** Database user (default: currencyuser)
4. **Database Password:** Secure database password
5. **Database Name:** Database name (default: currency_exchange)
6. **Domain Name:** Your domain (optional, for SSL setup)

## 🔒 Security Configuration

### Environment Variables Setup

The application now **requires** these environment variables:

```bash
# Required for security
SECRET_KEY=your-64-character-hex-secret
ADMIN_USERNAME=your-admin-username
ADMIN_PASSWORD=your-secure-password
DATABASE_URL=postgresql://user:pass@host:port/db

# Application settings
FLASK_ENV=production
DEBUG=false
PORT=5001
LOAD_SAMPLE_DATA=false
AWS_REGION=us-east-1
```

### Generate Secure Credentials

```bash
# Generate SECRET_KEY (64 characters)
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# Generate secure admin password
python3 -c "import secrets; print('ADMIN_PASSWORD=' + secrets.token_urlsafe(16))"

# Generate database password
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(20))"
```

## 🗄️ Database Setup

### Option 1: RDS PostgreSQL (Recommended)

1. **Create RDS Instance:**
   - Engine: PostgreSQL 14+
   - Instance class: db.t3.micro (testing) or db.t3.small (production)
   - Storage: 20GB GP3 SSD
   - Multi-AZ: Yes (for production)
   - Backup retention: 7 days

2. **Security Group Configuration:**
   ```
   Type        Protocol    Port    Source
   PostgreSQL  TCP         5432    EC2 Security Group
   ```

3. **Database URL Format:**
   ```
   postgresql://username:password@endpoint:5432/database_name
   ```

### Option 2: Local PostgreSQL

The deployment script can install PostgreSQL locally:

```bash
# Run deployment without --skip-db flag
sudo ./aws-deploy.sh
```

## 🌐 Domain and SSL Setup

### DNS Configuration

Point your domain to your EC2 instance:

```
Type    Name    Value
A       @       your-ec2-public-ip
A       www     your-ec2-public-ip
```

### SSL Certificate (Let's Encrypt)

After deployment with domain name:

```bash
# Install Certbot
sudo yum install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

## 🔍 Verification and Testing

### Check Service Status

```bash
# Check application service
sudo systemctl status currency-exchange

# Check Nginx
sudo systemctl status nginx

# Check application health
curl http://localhost:5001/health
```

### View Logs

```bash
# Application logs
sudo journalctl -u currency-exchange -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# System logs
sudo journalctl -f
```

### Test Web Access

1. **HTTP Access:** `http://your-ec2-public-ip`
2. **HTTPS Access:** `https://yourdomain.com` (if SSL configured)
3. **Health Check:** `http://your-ec2-public-ip/health`

## 🛠️ Post-Deployment Management

### Service Management

```bash
# Start/stop/restart application
sudo systemctl start currency-exchange
sudo systemctl stop currency-exchange
sudo systemctl restart currency-exchange

# Enable auto-start on boot
sudo systemctl enable currency-exchange

# Reload configuration after changes
sudo systemctl reload currency-exchange
```

### Application Updates

```bash
# Navigate to application directory
cd /opt/currency-exchange

# Pull latest changes
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python migrations.py

# Restart service
sudo systemctl restart currency-exchange
```

### Backup Strategy

```bash
# Create backup script
sudo tee /usr/local/bin/backup-currency-exchange.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup application files
tar -czf $BACKUP_DIR/app_$DATE.tar.gz -C /opt/currency-exchange .

# Backup database (if using local PostgreSQL)
sudo -u postgres pg_dump currency_exchange > $BACKUP_DIR/db_$DATE.sql

# Keep only last 7 backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-currency-exchange.sh

# Set up daily backup cron job
echo "0 2 * * * /usr/local/bin/backup-currency-exchange.sh" | sudo crontab -
```

## 🚨 Troubleshooting

### Common Issues

**1. Service Won't Start**
```bash
# Check service status and logs
sudo systemctl status currency-exchange
sudo journalctl -u currency-exchange --since '5 minutes ago'

# Check environment file
sudo cat /opt/currency-exchange/.env.production
```

**2. Database Connection Issues**
```bash
# Test database connection
PGPASSWORD=your_password psql -h your-rds-endpoint -U your_username -d currency_exchange -c "SELECT 1;"

# Check database URL in environment
grep DATABASE_URL /opt/currency-exchange/.env.production
```

**3. Nginx Configuration Issues**
```bash
# Test Nginx configuration
sudo nginx -t

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

**4. SSL Certificate Issues**
```bash
# Check certificate status
sudo certbot certificates

# Renew certificates manually
sudo certbot renew

# Test SSL configuration
openssl s_client -connect yourdomain.com:443
```

### Performance Monitoring

```bash
# Check system resources
htop
free -h
df -h

# Check application performance
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5001/health

# Monitor logs for errors
sudo journalctl -u currency-exchange -p err --since today
```

## 🔐 Security Hardening

### Firewall Configuration

```bash
# Install and configure firewall
sudo yum install -y firewalld
sudo systemctl enable firewalld
sudo systemctl start firewalld

# Allow necessary services
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

### System Updates

```bash
# Regular system updates
sudo yum update -y

# Update Python packages
cd /opt/currency-exchange
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart currency-exchange
```

### Security Monitoring

```bash
# Check for failed login attempts
sudo journalctl _COMM=sshd | grep "Failed password"

# Monitor application errors
sudo journalctl -u currency-exchange -p err --since today

# Check system security
sudo yum install -y aide
sudo aide --init
sudo aide --check
```

## 📊 Production Checklist

### Before Going Live:
- [ ] RDS database configured and accessible
- [ ] SSL certificate installed and working
- [ ] Domain DNS pointing to EC2 instance
- [ ] Secure credentials generated and set
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting configured
- [ ] Security groups properly configured
- [ ] Application tested end-to-end

### Post-Deployment:
- [ ] Health checks passing
- [ ] SSL certificate auto-renewal working
- [ ] Logs being generated properly
- [ ] Admin login working with secure credentials
- [ ] Database migrations completed
- [ ] Performance monitoring in place

## 🆘 Support

### Log Locations
- **Application:** `sudo journalctl -u currency-exchange`
- **Nginx:** `/var/log/nginx/`
- **System:** `sudo journalctl`

### Key Files
- **Application:** `/opt/currency-exchange/`
- **Environment:** `/opt/currency-exchange/.env.production`
- **Service:** `/etc/systemd/system/currency-exchange.service`
- **Nginx:** `/etc/nginx/conf.d/currency-exchange.conf`

### Quick Health Check
```bash
echo "Service: $(sudo systemctl is-active currency-exchange) | Nginx: $(sudo systemctl is-active nginx) | Health: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:5001/health)"
```

This deployment guide ensures a secure, production-ready deployment of your Currency Exchange application on AWS EC2.