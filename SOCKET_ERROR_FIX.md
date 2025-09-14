# Socket Error Fix Guide

## Problem Analysis

The "Bad file descriptor" error in gunicorn occurs when:
1. Clients disconnect before the response is sent
2. Socket timeouts due to poor configuration
3. Network connectivity issues
4. Improper handling of WebSocket connections with Flask-SocketIO

## Root Causes Identified

1. **Inadequate Gunicorn Configuration**: Single worker with no timeout settings
2. **Missing Error Handling**: No graceful handling of client disconnections
3. **Poor Nginx Configuration**: No timeout or buffer settings
4. **Lack of Monitoring**: No health checks or automatic recovery

## Solutions Implemented

### 1. Improved Gunicorn Configuration (`gunicorn.conf.py`)

```python
# Key improvements:
- timeout = 120                    # Prevent hanging requests
- keepalive = 5                   # Keep connections alive
- worker_connections = 1000       # Handle more concurrent connections
- graceful_timeout = 30           # Graceful worker shutdown
- reuse_port = True              # Better performance
```

### 2. Enhanced Flask App Error Handling

```python
# Added features:
- Comprehensive logging setup
- Error handlers for 500/404
- SocketIO error handlers
- Graceful shutdown signals
- Health check endpoint
```

### 3. Improved Nginx Configuration

```nginx
# Key settings:
proxy_connect_timeout 60s;       # Connection timeout
proxy_send_timeout 60s;          # Send timeout
proxy_read_timeout 60s;          # Read timeout
proxy_ignore_client_abort on;    # Handle disconnections gracefully
```

### 4. Monitoring and Health Checks

- Health check endpoint at `/health`
- Monitoring script (`monitor.sh`)
- Automatic service restart on failures
- Socket error detection and recovery

## Deployment Instructions

### 1. Update Your EC2 Instance

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Navigate to app directory
cd /opt/currency-exchange

# Pull the latest changes (including fixes)
git pull origin main

# Run the updated deployment script
./aws-deploy.sh
```

### 2. Verify the Fix

```bash
# Check service status
sudo systemctl status currency-exchange

# Check for socket errors in logs
sudo journalctl -u currency-exchange --since "1 hour ago" | grep -i "bad file descriptor"

# Test health endpoint
curl http://localhost/health

# Monitor real-time logs
sudo journalctl -u currency-exchange -f
```

### 3. Set Up Monitoring

```bash
# Make monitoring script executable
chmod +x /opt/currency-exchange/monitor.sh

# Test monitoring script
./monitor.sh

# Set up cron job for regular monitoring
echo "*/5 * * * * /opt/currency-exchange/monitor.sh" | sudo crontab -
```

## Expected Results

After implementing these fixes:

1. **Reduced Socket Errors**: Proper timeouts and error handling
2. **Better Performance**: Improved connection management
3. **Automatic Recovery**: Monitoring and restart capabilities
4. **Enhanced Logging**: Better visibility into issues

## Troubleshooting

### If Socket Errors Persist

1. **Check Network Connectivity**:
   ```bash
   # Test internal connectivity
   curl -I http://127.0.0.1:5001/health
   
   # Check nginx status
   sudo systemctl status nginx
   ```

2. **Increase Timeouts** (if needed):
   ```bash
   # Edit gunicorn.conf.py
   nano /opt/currency-exchange/gunicorn.conf.py
   # Increase timeout values
   ```

3. **Monitor Resource Usage**:
   ```bash
   # Check memory usage
   free -h
   
   # Check CPU usage
   top -p $(pgrep gunicorn)
   ```

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| High memory usage | Restart service: `sudo systemctl restart currency-exchange` |
| Database connection errors | Check RDS security group and connectivity |
| Nginx 502 errors | Verify gunicorn is running on port 5001 |
| SSL certificate issues | Run `sudo certbot renew` |

## Monitoring Commands

```bash
# Real-time monitoring
sudo journalctl -u currency-exchange -f

# Check recent errors
sudo journalctl -u currency-exchange --since "1 hour ago" | grep -i error

# Service status
sudo systemctl status currency-exchange nginx

# Health check
curl -s http://localhost/health | jq .

# Performance monitoring
ps aux | grep gunicorn
netstat -tlnp | grep :5001
```

## Prevention

1. **Regular Monitoring**: Use the monitoring script
2. **Log Rotation**: Ensure logs don't fill disk space
3. **Resource Monitoring**: Watch memory and CPU usage
4. **Regular Updates**: Keep dependencies updated
5. **Backup Strategy**: Regular database backups

The implemented fixes should significantly reduce or eliminate the "Bad file descriptor" errors while providing better monitoring and automatic recovery capabilities.