#!/bin/bash

# Currency Exchange Monitoring Script
# This script monitors the application and restarts services if needed

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVICE_NAME="currency-exchange"
LOG_FILE="/var/log/currency-exchange/monitor.log"
HEALTH_URL="http://localhost/health"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | sudo tee -a $LOG_FILE
}

# Function to check service status
check_service() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        return 0
    else
        return 1
    fi
}

# Function to check health endpoint
check_health() {
    response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL 2>/dev/null)
    if [ "$response" = "200" ]; then
        return 0
    else
        return 1
    fi
}

# Function to restart service
restart_service() {
    log_message "Restarting $SERVICE_NAME service..."
    sudo systemctl restart $SERVICE_NAME
    sleep 10
    
    if check_service; then
        log_message "Service restarted successfully"
        return 0
    else
        log_message "Failed to restart service"
        return 1
    fi
}

# Function to check for socket errors in logs
check_socket_errors() {
    error_count=$(sudo journalctl -u $SERVICE_NAME --since "5 minutes ago" | grep -c "Bad file descriptor" || echo 0)
    if [ "$error_count" -gt 5 ]; then
        log_message "High number of socket errors detected ($error_count), restarting service"
        restart_service
    fi
}

# Main monitoring loop
main() {
    log_message "Starting monitoring check..."
    
    # Check if service is running
    if ! check_service; then
        log_message "Service is not running, attempting to start..."
        sudo systemctl start $SERVICE_NAME
        sleep 10
    fi
    
    # Check health endpoint
    if ! check_health; then
        log_message "Health check failed, restarting service..."
        restart_service
    fi
    
    # Check for socket errors
    check_socket_errors
    
    # Check memory usage
    memory_usage=$(ps -o pid,ppid,cmd,%mem,%cpu --sort=-%mem -C gunicorn | awk 'NR>1 {sum+=$4} END {print sum}')
    if [ "${memory_usage%.*}" -gt 80 ]; then
        log_message "High memory usage detected (${memory_usage}%), restarting service"
        restart_service
    fi
    
    log_message "Monitoring check completed"
}

# Run the monitoring check
main

# If running with --daemon flag, run continuously
if [ "$1" = "--daemon" ]; then
    log_message "Starting monitoring daemon..."
    while true; do
        main
        sleep 300  # Check every 5 minutes
    done
fi