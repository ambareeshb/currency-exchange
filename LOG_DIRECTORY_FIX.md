# Log Directory Fix for Currency Exchange Service

## Problem Description

The `currency-exchange.service` was failing with the following error:

```
FileNotFoundError: [Errno 2] No such file or directory: '/var/log/gunicorn/error.log'
```

This error occurs when:
1. The `/var/log/gunicorn/` directory doesn't exist
2. Gunicorn tries to write to log files in that directory
3. The fallback mechanism in the gunicorn configuration wasn't working properly

## Root Cause Analysis

The issue was caused by:

1. **Missing Log Directory**: The `/var/log/gunicorn/` directory was not created during deployment
2. **Insufficient Fallback Logic**: The original gunicorn configuration had a basic fallback but it wasn't robust enough
3. **Permission Issues**: Even if the directory existed, there might be permission issues preventing log file creation

## Solution Implemented

### 1. Enhanced Gunicorn Configuration (`gunicorn.conf.py`)

Updated the logging configuration with:
- **Automatic Directory Creation**: Attempts to create the log directory if it doesn't exist
- **Permission Handling**: Tries to set proper ownership to `ec2-user`
- **Robust Fallback**: Falls back to stdout/stderr if file logging fails
- **Error Handling**: Gracefully handles permission errors and continues operation

### 2. Log Directory Fix Script (`fix_log_directories.sh`)

Created a comprehensive script that:
- Creates all required log directories (`/var/log/gunicorn`, `/var/log/currency-exchange`, `/var/run/gunicorn`)
- Sets proper ownership (`ec2-user:ec2-user`)
- Creates log files with correct permissions
- Verifies the setup
- Restarts the service safely

### 3. Updated Deployment Script (`aws-deploy.sh`)

The deployment script already had logic to create log directories, but the fix ensures:
- Directories are created during both initial setup and updates
- Log files are created with proper permissions
- The service can start even if log directory creation fails

## How to Apply the Fix

### On the EC2 Instance:

1. **Run the fix script** (recommended):
   ```bash
   sudo ./fix_log_directories.sh
   ```

2. **Manual fix** (if needed):
   ```bash
   # Create directories
   sudo mkdir -p /var/log/gunicorn /var/log/currency-exchange /var/run/gunicorn
   
   # Set ownership
   sudo chown ec2-user:ec2-user /var/log/gunicorn /var/log/currency-exchange /var/run/gunicorn
   
   # Create log files
   sudo touch /var/log/gunicorn/access.log /var/log/gunicorn/error.log
   sudo chown ec2-user:ec2-user /var/log/gunicorn/access.log /var/log/gunicorn/error.log
   sudo chmod 644 /var/log/gunicorn/access.log /var/log/gunicorn/error.log
   
   # Restart service
   sudo systemctl restart currency-exchange
   ```

3. **Verify the fix**:
   ```bash
   # Check service status
   sudo systemctl status currency-exchange
   
   # Check logs
   sudo journalctl -u currency-exchange -f
   
   # Verify log files
   ls -la /var/log/gunicorn/
   ```

## Prevention

To prevent this issue in the future:

1. **Use the updated deployment script**: The `aws-deploy.sh` script now ensures log directories are created during both initial setup and updates

2. **Monitor log directory permissions**: The enhanced gunicorn configuration will automatically handle missing directories

3. **Regular maintenance**: The fix script can be run periodically to ensure log directories remain properly configured

## Files Modified

1. **`gunicorn.conf.py`**: Enhanced logging configuration with robust fallback
2. **`fix_log_directories.sh`**: New script to fix log directory issues
3. **`aws-deploy.sh`**: Already had log directory creation logic (no changes needed)

## Testing

After applying the fix:

1. **Service should start successfully**:
   ```bash
   sudo systemctl status currency-exchange
   ```

2. **Logs should be written**:
   ```bash
   tail -f /var/log/gunicorn/error.log
   tail -f /var/log/gunicorn/access.log
   ```

3. **Service should survive restarts**:
   ```bash
   sudo systemctl restart currency-exchange
   sudo systemctl status currency-exchange
   ```

## Troubleshooting

If the service still fails after applying the fix:

1. **Check systemd logs**:
   ```bash
   sudo journalctl -u currency-exchange -n 50
   ```

2. **Verify file permissions**:
   ```bash
   ls -la /var/log/gunicorn/
   ls -la /var/run/gunicorn/
   ```

3. **Test gunicorn directly**:
   ```bash
   cd /opt/currency-exchange
   source venv/bin/activate
   ./venv/bin/gunicorn --config gunicorn.conf.py app:app
   ```

4. **Check for other issues**:
   - Database connectivity
   - Environment variables
   - Python dependencies
   - Port conflicts

## Summary

This fix addresses the log directory issue comprehensively by:
- ✅ Creating missing log directories automatically
- ✅ Setting proper permissions and ownership
- ✅ Providing robust fallback mechanisms
- ✅ Ensuring the service can start even with permission issues
- ✅ Making the solution maintainable for future deployments

The service should now start successfully and continue running without log-related errors.