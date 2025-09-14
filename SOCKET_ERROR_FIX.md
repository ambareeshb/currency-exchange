# Enhanced Socket Error Fix Guide

## Problem Analysis

The "Bad file descriptor" error in gunicorn occurs when:
1. Clients disconnect before the response is sent
2. Socket timeouts due to poor configuration
3. Network connectivity issues
4. Improper handling of WebSocket connections with Flask-SocketIO
5. File descriptor leaks in long-running processes
6. Memory pressure causing socket cleanup issues

## Root Causes Identified

1. **Inadequate Gunicorn Configuration**: Insufficient socket error handling
2. **Missing Error Handling**: No graceful handling of client disconnections
3. **Poor Nginx Configuration**: No timeout or buffer settings
4. **Lack of Monitoring**: No health checks or automatic recovery
5. **Resource Leaks**: File descriptors and memory not properly managed
6. **SocketIO Issues**: Improper error handling in real-time communications

## Enhanced Solutions Implemented

### 1. Advanced Gunicorn Configuration (`gunicorn.conf.py`)

```python
# Enhanced improvements:
- worker_connections = 500        # Reduced to prevent overload
- timeout = 60                    # Faster error detection
- keepalive = 2                   # Shorter keepalive
- max_requests = 500              # More frequent worker restarts
- graceful_timeout = 15           # Faster recovery
- Enhanced socket options with TCP keepalive
- Broken pipe signal handling
- Socket error recovery mechanisms
- Memory and file descriptor monitoring
```

### 2. Enhanced Flask App Error Handling

```python
# Advanced features:
- Socket error filtering and logging
- Enhanced SocketIO configuration
- Safe emission functions with error handling
- Comprehensive error recovery decorators
- Connection state management
- Graceful disconnection handling
```

### 3. Advanced SocketIO Error Handling

```python
# New features:
- Bad file descriptor error suppression
- Connection reset handling
- Broken pipe recovery
- Safe emission wrapper functions
- Enhanced connection lifecycle management
```

### 4. Comprehensive Monitoring and Recovery

- **Enhanced monitoring script** (`monitor.sh`)
- **Advanced socket recovery service** (`socket_recovery.py`)
- **Automated health checks** with multiple metrics
- **Process health monitoring** (memory, file descriptors)
- **Automatic service restart** with intelligent recovery
- **Log rotation** to prevent disk space issues
- **Systemd integration** with recovery services

## Enhanced Deployment Instructions

### 1. Update Your EC2 Instance

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Navigate to app directory
cd /opt/currency-exchange

# Pull the latest changes (including enhanced fixes)
git pull origin main

# Run the updated deployment script with enhanced recovery
./aws-deploy.sh
```

### 2. Verify the Enhanced Fix

```bash
# Check all service statuses
sudo systemctl status currency-exchange
sudo systemctl status currency-exchange-recovery
sudo systemctl status currency-exchange-recovery.timer

# Check for socket errors in logs
sudo journalctl -u currency-exchange --since "1 hour ago" | grep -i "bad file descriptor"

# Test health endpoint
curl http://localhost/health

# Monitor real-time logs with enhanced filtering
sudo journalctl -u currency-exchange -f | grep -E "(socket|error|recovery)"

# Check socket recovery logs
sudo journalctl -u currency-exchange-recovery -f
```

### 3. Enhanced Monitoring Setup

```bash
# Scripts are automatically made executable by deployment
# Test enhanced monitoring script
./monitor.sh

# Test socket recovery script
python3 socket_recovery.py

# Verify systemd services are enabled
sudo systemctl list-unit-files | grep currency-exchange

# Check timer status
sudo systemctl status currency-exchange-recovery.timer
```

### 4. Advanced Monitoring Commands

```bash
# Real-time socket error monitoring
sudo journalctl -u currency-exchange -f | grep -E "(Bad file descriptor|Broken pipe|Connection reset)"

# Process health monitoring
ps aux | grep gunicorn
lsof -p $(pgrep -f "gunicorn.*currency-exchange")

# Memory and file descriptor usage
cat /proc/$(pgrep -f "gunicorn.*currency-exchange")/status | grep -E "(VmRSS|FDSize)"

# Socket recovery service logs
sudo journalctl -u currency-exchange-recovery --since "1 hour ago"
```

## Expected Results

After implementing these enhanced fixes:

1. **Eliminated Socket Errors**: Advanced error handling and recovery
2. **Superior Performance**: Optimized connection management and resource usage
3. **Intelligent Recovery**: Multi-layered monitoring and automatic restart
4. **Comprehensive Logging**: Detailed visibility with error categorization
5. **Proactive Monitoring**: Predictive failure detection and prevention
6. **Resource Management**: Memory and file descriptor leak prevention
7. **High Availability**: Minimal downtime with fast recovery mechanisms

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

## Enhanced Prevention Strategy

1. **Multi-layered Monitoring**: Enhanced monitoring script + socket recovery service
2. **Automated Log Management**: Log rotation and cleanup to prevent disk issues
3. **Proactive Resource Monitoring**: Memory, CPU, and file descriptor tracking
4. **Intelligent Recovery**: Automatic service restart with failure analysis
5. **Regular Health Checks**: Continuous application and database monitoring
6. **Performance Optimization**: Regular dependency updates and configuration tuning
7. **Comprehensive Backup Strategy**: Database and configuration backups
8. **Error Pattern Analysis**: Trend analysis for predictive maintenance

## New Recovery Features

### Socket Recovery Service
- **Automatic Detection**: Monitors for socket errors in real-time
- **Intelligent Restart**: Restarts services only when necessary
- **Resource Cleanup**: Removes stale socket files and processes
- **Health Verification**: Confirms service recovery after restart

### Enhanced Monitoring
- **Process Health**: Memory usage, file descriptor counts
- **Socket Error Tracking**: Categorized error counting and analysis
- **Performance Metrics**: Response time and connection monitoring
- **Predictive Alerts**: Early warning system for potential issues

### Systemd Integration
- **Service Dependencies**: Proper service ordering and dependencies
- **Resource Limits**: Memory and CPU constraints to prevent resource exhaustion
- **Automatic Restart**: Enhanced restart policies with backoff
- **Timer-based Checks**: Regular health verification

The enhanced implementation provides a robust, self-healing system that should completely eliminate "Bad file descriptor" errors while maintaining high availability and performance.