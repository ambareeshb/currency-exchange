# AWS Deployment Guide - How to Use aws-deploy.sh

This guide explains how to use the `aws-deploy.sh` script to deploy the Currency Exchange application on AWS EC2.

## Prerequisites

### 1. AWS EC2 Instance Setup
- Launch an Amazon Linux 2 EC2 instance
- Instance type: t3.micro or larger (t3.small recommended for production)
- Security Group: Allow HTTP (80), HTTPS (443), and SSH (22)
- Key pair for SSH access

### 2. Connect to Your EC2 Instance
```bash
ssh -i your-key.pem ec2-user@your-ec2-public-ip
```

### 3. Prepare Your Application Code
You have two options:

#### Option A: Upload from Local Machine
```bash
# From your local machine, upload the application
scp -i your-key.pem -r /path/to/currency-exchange ec2-user@your-ec2-ip:/home/ec2-user/
```

#### Option B: Clone from Git Repository
```bash
# On the EC2 instance
git clone https://github.com/your-username/currency-exchange.git
cd currency-exchange
```

## Deployment Steps

### Step 1: Make the Script Executable
```bash
chmod +x aws-deploy.sh
```

### Step 2: Run the Deployment Script

#### Basic Deployment (Recommended)
```bash
sudo ./aws-deploy.sh
```

This will install everything including:
- Database setup (local PostgreSQL)
- SSL certificates
- Monitoring tools
- Security configurations

#### Advanced Deployment Options

##### Skip Database Setup (if using RDS)
```bash
sudo ./aws-deploy.sh --skip-db
```

##### Skip SSL Setup (for testing)
```bash
sudo ./aws-deploy.sh --skip-ssl
```

##### Skip Monitoring Setup
```bash
sudo ./aws-deploy.sh --skip-monitoring
```

##### Set Environment
```bash
sudo ./aws-deploy.sh --environment staging
```

##### Combine Multiple Options
```bash
sudo ./aws-deploy.sh --skip-db --skip-ssl --environment development
```

##### View Help
```bash
./aws-deploy.sh --help
```

## Configuration

### Step 3: Configure Environment Variables
After deployment, edit the environment file:

```bash
sudo nano /opt/currency-exchange/.env.aws
```

**Important configurations to update:**

```bash
# Change the secret key
SECRET_KEY=your-secure-secret-key-here

# Update database URL (if using RDS)
DATABASE_URL=postgresql://username:password@your-rds-endpoint.region.rds.amazonaws.com:5432/currency_exchange

# Set admin credentials
ADMIN_USERNAME=your-admin-username
ADMIN_PASSWORD=your-secure-password

# Set AWS region
AWS_REGION=us-east-1
```

### Step 4: Restart the Service
After configuration changes:

```bash
sudo systemctl restart currency-exchange
```

## Verification

### Check Service Status
```bash
sudo systemctl status currency-exchange
```

### Check Application Health
```bash
curl http://localhost:5001/health
```

### View Logs
```bash
sudo journalctl -u currency-exchange -f
```

### Test Web Access
Open your browser and navigate to:
- `http://your-ec2-public-ip` (HTTP)
- `https://your-ec2-public-ip` (HTTPS, if SSL was configured)

## Post-Deployment Management

### Service Management
```bash
# Start the service
sudo systemctl start currency-exchange

# Stop the service
sudo systemctl stop currency-exchange

# Restart the service
sudo systemctl restart currency-exchange

# Check service status
sudo systemctl status currency-exchange

# Enable auto-start on boot
sudo systemctl enable currency-exchange
```

### Log Management
```bash
# View real-time logs
sudo journalctl -u currency-exchange -f

# View all logs
sudo journalctl -u currency-exchange

# View logs from last hour
sudo journalctl -u currency-exchange --since '1 hour ago'

# View only error logs
sudo journalctl -u currency-exchange -p err

# View logs from specific date
sudo journalctl -u currency-exchange --since '2025-01-15 10:00:00'
```

### Backup Management
```bash
# Manual backup
sudo /usr/local/bin/backup-currency-exchange.sh

# List backups
ls -la /opt/backups/

# Restore from backup (example)
sudo tar -xzf /opt/backups/app_20250115_120000.tar.gz -C /opt/currency-exchange/
```

### Monitoring
```bash
# Check application health
curl http://localhost:5001/health

# Monitor system resources
htop

# Check nginx status
sudo systemctl status nginx

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start
```bash
# Check service status
sudo systemctl status currency-exchange

# View recent logs
sudo journalctl -u currency-exchange --since '5 minutes ago'

# Check configuration
sudo systemctl cat currency-exchange
```

#### 2. Database Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test database connection
sudo -u postgres psql -c "SELECT 1;"

# Check database configuration in .env.aws
sudo cat /opt/currency-exchange/.env.aws | grep DATABASE_URL
```

#### 3. Nginx Issues
```bash
# Test nginx configuration
sudo nginx -t

# Check nginx status
sudo systemctl status nginx

# View nginx error logs
sudo tail -f /var/log/nginx/error.log
```

#### 4. SSL Certificate Issues
```bash
# Check certificate status
sudo certbot certificates

# Renew certificates
sudo certbot renew

# Test SSL configuration
curl -I https://your-domain.com
```

### Log Analysis
```bash
# Check for errors in the last 10 minutes
sudo journalctl -u currency-exchange --since '10 minutes ago' -p err

# Count error occurrences today
sudo journalctl -u currency-exchange --since today | grep -c "ERROR"

# Search for specific error patterns
sudo journalctl -u currency-exchange | grep "database"
sudo journalctl -u currency-exchange | grep "connection"
```

## Security Considerations

### 1. Update Default Passwords
- Change admin password in `.env.aws`
- Update database passwords
- Generate new secret keys

### 2. Configure Firewall
```bash
# Install and configure firewall (optional)
sudo yum install -y firewalld
sudo systemctl enable firewalld
sudo systemctl start firewalld

# Allow necessary ports
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

### 3. Regular Updates
```bash
# Update system packages
sudo yum update -y

# Update Python dependencies
cd /opt/currency-exchange
sudo -u ec2-user ./venv/bin/pip install --upgrade -r requirements.txt
sudo systemctl restart currency-exchange
```

## Scaling and Production Considerations

### 1. Database (RDS)
For production, use Amazon RDS instead of local PostgreSQL:
- Create RDS PostgreSQL instance
- Update `DATABASE_URL` in `.env.aws`
- Run deployment with `--skip-db` flag

### 2. Load Balancer
For high availability:
- Use Application Load Balancer (ALB)
- Deploy multiple EC2 instances
- Configure health checks pointing to `/health`

### 3. Monitoring
- Set up CloudWatch for metrics
- Configure log forwarding to CloudWatch Logs
- Set up alerts for error rates and response times

### 4. Backup Strategy
- Use RDS automated backups
- Configure S3 for application file backups
- Set up cross-region backup replication

## Support Commands

### Quick Status Check
```bash
# One-liner to check everything
echo "Service: $(sudo systemctl is-active currency-exchange) | Nginx: $(sudo systemctl is-active nginx) | Health: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:5001/health)"
```

### Performance Monitoring
```bash
# Check resource usage
sudo systemctl status currency-exchange --no-pager -l
ps aux | grep gunicorn
free -h
df -h
```

### Configuration Backup
```bash
# Backup all configuration files
sudo tar -czf /opt/backups/config-backup-$(date +%Y%m%d).tar.gz \
  /opt/currency-exchange/.env.aws \
  /etc/systemd/system/currency-exchange.service \
  /etc/nginx/conf.d/currency-exchange.conf \
  /opt/currency-exchange/gunicorn.conf.py
```

This guide covers all aspects of deploying and managing the Currency Exchange application using the `aws-deploy.sh` script. For additional support, check the systemd journal logs and the application's health endpoint.