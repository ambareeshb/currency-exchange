# Systemd Journal Logging Setup

This document describes the systemd journal logging configuration for the Currency Exchange application on AWS EC2.

## Overview

The application has been configured to use systemd journal for centralized logging instead of file-based logging. This provides better log management, rotation, and integration with system monitoring tools.

## Configuration Changes

### 1. Gunicorn Configuration (`gunicorn.conf.py`)

- **Access Log**: `accesslog = "-"` (stdout)
- **Error Log**: `errorlog = "-"` (stderr)
- **Capture Output**: `capture_output = True`
- **Syslog Integration**: `disable_redirect_access_to_syslog = False`

All application logs are sent to stdout/stderr, which systemd automatically captures to the journal.

### 2. Systemd Service (`currency-exchange.service`)

```ini
[Service]
StandardOutput=journal
StandardError=journal
SyslogIdentifier=currency-exchange
```

This configuration ensures:
- All stdout goes to systemd journal
- All stderr goes to systemd journal
- Logs are tagged with `currency-exchange` identifier

### 3. Application Logging

The Flask application logs are automatically captured through gunicorn's stdout/stderr redirection.

## Deployment

### Automatic Deployment

Use the provided deployment script:

```bash
sudo ./aws-deploy.sh
```

### Manual Deployment

1. Copy the systemd service file:
```bash
sudo cp currency-exchange.service /etc/systemd/system/
sudo systemctl daemon-reload
```

2. Enable and start the service:
```bash
sudo systemctl enable currency-exchange
sudo systemctl start currency-exchange
```

## Log Management

### Viewing Logs

#### Real-time log monitoring:
```bash
sudo journalctl -u currency-exchange -f
```

#### View all logs for the service:
```bash
sudo journalctl -u currency-exchange
```

#### View logs from the last hour:
```bash
sudo journalctl -u currency-exchange --since '1 hour ago'
```

#### View logs from a specific date:
```bash
sudo journalctl -u currency-exchange --since '2025-01-15 10:00:00'
```

#### View logs with specific priority (error, warning, info):
```bash
sudo journalctl -u currency-exchange -p err
sudo journalctl -u currency-exchange -p warning
sudo journalctl -u currency-exchange -p info
```

### Log Filtering

#### Filter by specific keywords:
```bash
sudo journalctl -u currency-exchange | grep "ERROR"
sudo journalctl -u currency-exchange | grep "database"
```

#### Show only the last 100 lines:
```bash
sudo journalctl -u currency-exchange -n 100
```

#### Follow logs with timestamp:
```bash
sudo journalctl -u currency-exchange -f --output=short-iso
```

### Log Rotation and Retention

Systemd journal automatically handles log rotation. Configure retention with:

```bash
# Edit journald configuration
sudo nano /etc/systemd/journald.conf
```

Recommended settings:
```ini
[Journal]
SystemMaxUse=1G
SystemKeepFree=500M
SystemMaxFileSize=100M
MaxRetentionSec=30day
```

Apply changes:
```bash
sudo systemctl restart systemd-journald
```

## Service Management

### Service Status
```bash
sudo systemctl status currency-exchange
```

### Start/Stop/Restart
```bash
sudo systemctl start currency-exchange
sudo systemctl stop currency-exchange
sudo systemctl restart currency-exchange
```

### Enable/Disable auto-start
```bash
sudo systemctl enable currency-exchange
sudo systemctl disable currency-exchange
```

### Reload configuration
```bash
sudo systemctl reload currency-exchange
```

## Monitoring and Alerting

### Check service health
```bash
# Service status
sudo systemctl is-active currency-exchange

# Application health endpoint
curl http://localhost:5001/health
```

### Log-based monitoring
```bash
# Check for errors in the last 10 minutes
sudo journalctl -u currency-exchange --since '10 minutes ago' -p err

# Count error occurrences
sudo journalctl -u currency-exchange --since today | grep -c "ERROR"
```

### Integration with monitoring tools

The systemd journal can be integrated with:
- **Prometheus**: Using `node_exporter` with `--collector.systemd`
- **Grafana**: For log visualization
- **ELK Stack**: Using `journalbeat`
- **CloudWatch**: Using CloudWatch agent

## Troubleshooting

### Service won't start
```bash
# Check service status
sudo systemctl status currency-exchange

# Check recent logs
sudo journalctl -u currency-exchange --since '5 minutes ago'

# Check configuration
sudo systemctl cat currency-exchange
```

### High log volume
```bash
# Check journal disk usage
sudo journalctl --disk-usage

# Vacuum old logs
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=500M
```

### Permission issues
```bash
# Check service user permissions
sudo -u ec2-user ls -la /opt/currency-exchange

# Check systemd service file permissions
ls -la /etc/systemd/system/currency-exchange.service
```

## Security Considerations

The systemd service includes security hardening:
- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `PrivateDevices=true`
- `PrivateTmp=true`

Logs are stored in `/var/log/journal/` with appropriate permissions and are only accessible to root and the systemd-journal group.

## Benefits of Systemd Journal Logging

1. **Centralized**: All system and application logs in one place
2. **Structured**: Binary format with metadata
3. **Efficient**: Better performance than text-based logs
4. **Integrated**: Works seamlessly with systemd services
5. **Secure**: Built-in access controls and integrity checking
6. **Queryable**: Rich filtering and search capabilities
7. **Automatic rotation**: No manual log rotation setup needed

## Migration from File-based Logging

If migrating from file-based logging:

1. Old log files in `/var/log/gunicorn/` are no longer used
2. All logs are now in systemd journal
3. Update any log monitoring scripts to use `journalctl`
4. Update log rotation scripts (no longer needed)
5. Update backup scripts to include journal if needed

## Performance Impact

Systemd journal logging has minimal performance impact:
- Binary format is more efficient than text
- Automatic compression reduces disk usage
- In-memory buffering improves write performance
- No file locking issues with multiple processes