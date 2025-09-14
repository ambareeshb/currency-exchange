# Logging Troubleshooting Guide

## Overview
This guide helps troubleshoot logging issues with the Currency Exchange application, particularly when you encounter "internal server error but there are no logs" situations.

## Quick Diagnosis

### 1. Check Log File Locations
```bash
# Application logs
ls -la /var/log/currency-exchange/app.log

# Gunicorn logs
ls -la /var/log/gunicorn/access.log
ls -la /var/log/gunicorn/error.log

# Check permissions
ls -la /var/log/currency-exchange/
ls -la /var/log/gunicorn/
```

### 2. Check Recent Logs
```bash
# Application logs
sudo tail -f /var/log/currency-exchange/app.log

# Gunicorn error logs
sudo tail -f /var/log/gunicorn/error.log

# Systemd journal logs
sudo journalctl -u currency-exchange -f

# All recent logs
sudo journalctl -u currency-exchange --no-pager -n 50
```

### 3. Test Application Logging
```bash
# Test if logging is working
echo "$(date): Test log entry" | sudo tee -a /var/log/currency-exchange/app.log

# Check if the application can write to logs
sudo -u ec2-user touch /var/log/currency-exchange/test.log
```

## Common Issues and Solutions

### Issue 1: Log Directories Don't Exist
**Symptoms:** No logs appear anywhere, application may fail to start

**Solution:**
```bash
# Create log directories
sudo mkdir -p /var/log/currency-exchange
sudo mkdir -p /var/log/gunicorn
sudo mkdir -p /var/run/gunicorn

# Set proper ownership
sudo chown -R ec2-user:ec2-user /var/log/currency-exchange
sudo chown -R ec2-user:ec2-user /var/log/gunicorn
sudo chown -R ec2-user:ec2-user /var/run/gunicorn

# Set proper permissions
sudo chmod -R 755 /var/log/currency-exchange
sudo chmod -R 755 /var/log/gunicorn
sudo chmod -R 755 /var/run/gunicorn
```

### Issue 2: Permission Denied Errors
**Symptoms:** Application starts but no logs are written, permission errors in systemd journal

**Solution:**
```bash
# Fix log file permissions
sudo touch /var/log/currency-exchange/app.log
sudo touch /var/log/gunicorn/access.log
sudo touch /var/log/gunicorn/error.log

sudo chown ec2-user:ec2-user /var/log/currency-exchange/app.log
sudo chown ec2-user:ec2-user /var/log/gunicorn/access.log
sudo chown ec2-user:ec2-user /var/log/gunicorn/error.log

sudo chmod 644 /var/log/currency-exchange/app.log
sudo chmod 644 /var/log/gunicorn/access.log
sudo chmod 644 /var/log/gunicorn/error.log
```

### Issue 3: Logs Not Rotating
**Symptoms:** Log files grow very large, disk space issues

**Solution:**
```bash
# Check logrotate configuration
sudo cat /etc/logrotate.d/currency-exchange

# Manually rotate logs if needed
sudo logrotate -f /etc/logrotate.d/currency-exchange

# Check disk space
df -h /var/log/
```

### Issue 4: Application Errors Not Logged
**Symptoms:** Internal server errors but no error details in logs

**Solution:**
1. Check if the enhanced error handlers are working:
```bash
# Look for error patterns in logs
sudo grep -i "error\|exception\|traceback" /var/log/currency-exchange/app.log
sudo grep -i "error\|exception\|traceback" /var/log/gunicorn/error.log
```

2. Test error logging:
```bash
# Restart application with verbose logging
sudo systemctl stop currency-exchange
cd /opt/currency-exchange
source venv/bin/activate
export $(cat .env.production | grep -v '^#' | xargs)
python3 app.py  # Run directly to see console output
```

3. Check if the logging configuration is properly loaded:
```bash
# Look for logging setup messages
sudo grep -i "logging\|log file" /var/log/currency-exchange/app.log
```

## Logging Configuration Details

### Application Logging (app.py)
- **Location:** `/var/log/currency-exchange/app.log`
- **Fallback:** Local `app.log` file if directory doesn't exist
- **Format:** `%(asctime)s %(levelname)s %(name)s %(message)s`
- **Level:** INFO and above

### Gunicorn Logging (gunicorn.conf.py)
- **Access Log:** `/var/log/gunicorn/access.log`
- **Error Log:** `/var/log/gunicorn/error.log`
- **Fallback:** stdout/stderr if directory doesn't exist

### Systemd Journal
- **View logs:** `sudo journalctl -u currency-exchange`
- **Follow logs:** `sudo journalctl -u currency-exchange -f`
- **Recent logs:** `sudo journalctl -u currency-exchange --no-pager -n 50`

## Emergency Logging Recovery

If all logging fails, use this emergency procedure:

```bash
# 1. Stop the service
sudo systemctl stop currency-exchange

# 2. Run the logging setup from deployment script
cd /opt/currency-exchange
sudo mkdir -p /var/log/currency-exchange /var/log/gunicorn /var/run/gunicorn
sudo chown -R ec2-user:ec2-user /var/log/currency-exchange /var/log/gunicorn /var/run/gunicorn
sudo chmod -R 755 /var/log/currency-exchange /var/log/gunicorn /var/run/gunicorn

# 3. Create log files
sudo touch /var/log/currency-exchange/app.log
sudo touch /var/log/gunicorn/access.log
sudo touch /var/log/gunicorn/error.log
sudo chown ec2-user:ec2-user /var/log/currency-exchange/app.log
sudo chown ec2-user:ec2-user /var/log/gunicorn/access.log
sudo chown ec2-user:ec2-user /var/log/gunicorn/error.log
sudo chmod 644 /var/log/currency-exchange/app.log
sudo chmod 644 /var/log/gunicorn/access.log
sudo chmod 644 /var/log/gunicorn/error.log

# 4. Test logging
echo "$(date): Emergency logging recovery completed" | tee -a /var/log/currency-exchange/app.log

# 5. Restart service
sudo systemctl start currency-exchange

# 6. Verify logs are working
sudo tail -f /var/log/currency-exchange/app.log
```

## Monitoring Commands

### Real-time Log Monitoring
```bash
# Watch all logs simultaneously
sudo tail -f /var/log/currency-exchange/app.log /var/log/gunicorn/error.log

# Monitor systemd journal
sudo journalctl -u currency-exchange -f

# Monitor with timestamps
sudo journalctl -u currency-exchange -f --output=short-iso
```

### Log Analysis
```bash
# Count error types
sudo grep -c "ERROR" /var/log/currency-exchange/app.log
sudo grep -c "WARNING" /var/log/currency-exchange/app.log

# Find recent errors
sudo grep "ERROR\|CRITICAL" /var/log/currency-exchange/app.log | tail -10

# Check application startup
sudo grep "Starting Currency Exchange" /var/log/currency-exchange/app.log
```

## Prevention

### Regular Maintenance
1. **Monitor disk space:** `df -h /var/log/`
2. **Check log rotation:** `sudo logrotate -d /etc/logrotate.d/currency-exchange`
3. **Verify permissions weekly:** `ls -la /var/log/currency-exchange/ /var/log/gunicorn/`

### Automated Monitoring
The deployment script includes log verification. Run it periodically:
```bash
cd /opt/currency-exchange
./aws-deploy.sh  # Will verify and fix logging setup
```

## Contact Information
If logging issues persist after following this guide, check:
1. System disk space: `df -h`
2. SELinux status: `sestatus` (if applicable)
3. System logs: `sudo journalctl --no-pager -n 100`