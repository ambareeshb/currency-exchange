# AWS EC2 Deployment Guide

## Overview
Deploy the Currency Exchange app to AWS EC2 using free tier services.

**Cost**: Free for 12 months, then ~$28/month

## Prerequisites
- AWS Account with free tier eligibility
- Domain name (optional)
- SSH key pair

## Quick Setup

### 1. Create RDS Database
1. Go to **RDS Console** → **Create Database**
2. Configure:
   - **Engine**: PostgreSQL (Free tier)
   - **Instance**: db.t3.micro
   - **Database name**: `currency_exchange`
   - **Username**: `currencyuser`
   - **Public access**: Yes

### 2. Launch EC2 Instance
1. Go to **EC2 Console** → **Launch Instance**
2. Configure:
   - **AMI**: Amazon Linux 2023
   - **Instance Type**: t2.micro (free tier)
   - **Security Group**: Allow SSH (22), HTTP (80), HTTPS (443)
3. **Allocate Elastic IP** and associate with instance

### 3. Automated Deployment
```bash
# Connect to EC2
ssh -i your-key.pem ec2-user@your-ec2-ip

# Download and run deployment script
curl -O https://raw.githubusercontent.com/yourusername/currency-exchange/main/aws-deploy.sh
chmod +x aws-deploy.sh
./aws-deploy.sh
```

The script will prompt for:
- GitHub repository URL
- RDS endpoint and credentials
- Domain name (optional)

### 4. DNS & SSL Setup
Configure DNS A record to point to your Elastic IP:
```
Type: A
Host: @
Value: Your-Elastic-IP
TTL: 3600
```

Setup SSL certificate:
```bash
sudo snap install --classic certbot
sudo certbot --nginx -d yourdomain.com
```

## File Structure
After deployment, files are located in `/opt/currency-exchange/`:
```
/opt/currency-exchange/
├── app.py                    # Main Flask application
├── migrations.py             # Database migrations
├── requirements.txt          # Dependencies
├── .env.production          # Environment variables (server only)
├── venv/                    # Python virtual environment
└── templates/               # HTML templates
```

## Architecture
```
Internet → DNS → EC2 Elastic IP → Nginx (80/443) → Flask App (5001) → RDS PostgreSQL
```

### Why Nginx + Gunicorn?
- **Security**: Nginx filters malicious requests
- **Performance**: Nginx handles static files and connections efficiently
- **SSL**: Easy HTTPS setup with Let's Encrypt
- **Reliability**: Better error handling and recovery

## Management Commands

### Deploy Updates
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
cd /opt/currency-exchange
./aws-deploy.sh
```

### Service Management
```bash
# Check status
sudo systemctl status currency-exchange

# Restart services
sudo systemctl restart currency-exchange nginx

# View logs
sudo journalctl -u currency-exchange -f
```

### Database Access
```bash
psql -h your-rds-endpoint -U currencyuser -d currency_exchange
```

## Troubleshooting

### Common Issues
1. **Service not starting**: Check logs with `sudo journalctl -u currency-exchange`
2. **Database connection**: Verify RDS security group allows EC2 access
3. **Environment variables**: Ensure `.env.production` has correct values

### Manual Migration
```bash
cd /opt/currency-exchange
source venv/bin/activate
python migrations.py
```

## Security Checklist
- [ ] Change default admin credentials
- [ ] Restrict SSH access to your IP
- [ ] Enable HTTPS with SSL certificate
- [ ] Configure automated backups
- [ ] Set up monitoring

Your app will be available at:
- **Domain**: `https://yourdomain.com`
- **IP**: `http://your-elastic-ip`

Admin credentials are displayed during initial setup.