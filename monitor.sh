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

# Enhanced function to check for socket errors in logs
check_socket_errors() {
    # Check for various socket-related errors
    bad_fd_count=$(sudo journalctl -u $SERVICE_NAME --since "5 minutes ago" | grep -c "Bad file descriptor" || echo 0)
    broken_pipe_count=$(sudo journalctl -u $SERVICE_NAME --since "5 minutes ago" | grep -c "Broken pipe" || echo 0)
    connection_reset_count=$(sudo journalctl -u $SERVICE_NAME --since "5 minutes ago" | grep -c "Connection reset by peer" || echo 0)
    
    total_socket_errors=$((bad_fd_count + broken_pipe_count + connection_reset_count))
    
    log_message "Socket error counts - Bad FD: $bad_fd_count, Broken pipe: $broken_pipe_count, Connection reset: $connection_reset_count"
    
    # Restart if too many socket errors
    if [ "$total_socket_errors" -gt 10 ]; then
        log_message "High number of socket errors detected ($total_socket_errors), restarting service"
        restart_service
    elif [ "$bad_fd_count" -gt 3 ]; then
        log_message "Multiple bad file descriptor errors ($bad_fd_count), restarting service"
        restart_service
    fi
}

# Function to check worker process health
check_worker_health() {
    # Check if gunicorn workers are responsive
    worker_pids=$(pgrep -f "gunicorn.*currency-exchange" || echo "")
    
    if [ -z "$worker_pids" ]; then
        log_message "No gunicorn workers found, service may be down"
        return 1
    fi
    
    # Check for zombie processes
    zombie_count=$(ps aux | grep -c "[Zz]ombie.*gunicorn" || echo 0)
    if [ "$zombie_count" -gt 0 ]; then
        log_message "Zombie gunicorn processes detected ($zombie_count), restarting service"
        restart_service
    fi
    
    # Check worker memory usage
    for pid in $worker_pids; do
        if [ -d "/proc/$pid" ]; then
            memory_kb=$(ps -o rss= -p $pid 2>/dev/null || echo 0)
            memory_mb=$((memory_kb / 1024))
            if [ "$memory_mb" -gt 500 ]; then
                log_message "Worker $pid using excessive memory (${memory_mb}MB), restarting service"
                restart_service
                break
            fi
        fi
    done
}

# Function to check socket file descriptors
check_socket_descriptors() {
    # Check for too many open file descriptors
    for pid in $(pgrep -f "gunicorn.*currency-exchange" || echo ""); do
        if [ -d "/proc/$pid/fd" ]; then
            fd_count=$(ls /proc/$pid/fd 2>/dev/null | wc -l || echo 0)
            if [ "$fd_count" -gt 1000 ]; then
                log_message "Process $pid has too many file descriptors ($fd_count), restarting service"
                restart_service
                break
            fi
        fi
    done
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
    
    # Enhanced monitoring checks
    
    # Check for socket errors
    check_socket_errors
    
    # Check worker health
    check_worker_health
    
    # Check socket descriptors
    check_socket_descriptors
    
    # Check memory usage with better calculation
    memory_usage=$(ps -o pid,ppid,cmd,%mem,%cpu --sort=-%mem -C gunicorn 2>/dev/null | awk 'NR>1 {sum+=$4} END {print sum+0}')
    if [ "${memory_usage%.*}" -gt 80 ]; then
        log_message "High memory usage detected (${memory_usage}%), restarting service"
        restart_service
    fi
    
    # Check disk space for logs
    log_disk_usage=$(df /var/log | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$log_disk_usage" -gt 90 ]; then
        log_message "Log disk usage high (${log_disk_usage}%), cleaning old logs"
        # Clean logs older than 7 days
        find /var/log/gunicorn -name "*.log" -mtime +7 -delete 2>/dev/null || true
        find /var/log/currency-exchange -name "*.log" -mtime +7 -delete 2>/dev/null || true
    fi
    
    # Check for core dumps
    core_dumps=$(find /tmp -name "core.*" -o -name "python*core*" 2>/dev/null | wc -l)
    if [ "$core_dumps" -gt 0 ]; then
        log_message "Core dumps detected ($core_dumps), cleaning up and restarting service"
        find /tmp -name "core.*" -o -name "python*core*" -delete 2>/dev/null || true
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