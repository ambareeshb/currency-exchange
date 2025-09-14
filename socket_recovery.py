#!/usr/bin/env python3
"""
Socket Error Recovery Script for Currency Exchange App
This script provides advanced socket error detection and recovery mechanisms.
"""

import os
import sys
import time
import signal
import psutil
import logging
import subprocess
import socket
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/currency-exchange/socket_recovery.log')
    ]
)

logger = logging.getLogger(__name__)

class SocketRecoveryManager:
    def __init__(self):
        self.service_name = "currency-exchange"
        self.app_port = 5001
        self.max_socket_errors = 5
        self.check_interval = 30  # seconds
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3
        
    def check_service_status(self):
        """Check if the service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', self.service_name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking service status: {e}")
            return False
    
    def check_port_availability(self):
        """Check if the application port is responding"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('127.0.0.1', self.app_port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.warning(f"Port check failed: {e}")
            return False
    
    def check_socket_errors(self):
        """Check for socket errors in recent logs"""
        try:
            # Check journalctl for socket errors in the last 5 minutes
            result = subprocess.run([
                'journalctl', '-u', self.service_name, 
                '--since', '5 minutes ago', '--no-pager'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("Could not read service logs")
                return 0
            
            log_content = result.stdout
            
            # Count different types of socket errors
            bad_fd_count = log_content.count('Bad file descriptor')
            broken_pipe_count = log_content.count('Broken pipe')
            connection_reset_count = log_content.count('Connection reset by peer')
            
            total_errors = bad_fd_count + broken_pipe_count + connection_reset_count
            
            if total_errors > 0:
                logger.info(f"Socket errors found - Bad FD: {bad_fd_count}, "
                          f"Broken pipe: {broken_pipe_count}, "
                          f"Connection reset: {connection_reset_count}")
            
            return total_errors
            
        except Exception as e:
            logger.error(f"Error checking socket errors: {e}")
            return 0
    
    def check_process_health(self):
        """Check the health of gunicorn processes"""
        try:
            gunicorn_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'num_fds']):
                try:
                    if 'gunicorn' in proc.info['name'] and 'currency-exchange' in ' '.join(proc.info['cmdline']):
                        gunicorn_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not gunicorn_processes:
                logger.warning("No gunicorn processes found")
                return False
            
            # Check each process
            for proc in gunicorn_processes:
                try:
                    # Check memory usage (restart if > 500MB)
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                    if memory_mb > 500:
                        logger.warning(f"Process {proc.pid} using excessive memory: {memory_mb:.1f}MB")
                        return False
                    
                    # Check file descriptors (restart if > 1000)
                    if proc.info['num_fds'] > 1000:
                        logger.warning(f"Process {proc.pid} has too many file descriptors: {proc.info['num_fds']}")
                        return False
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking process health: {e}")
            return False
    
    def restart_service(self):
        """Restart the service with enhanced recovery"""
        logger.info("Attempting service restart...")
        
        try:
            # Stop the service
            subprocess.run(['systemctl', 'stop', self.service_name], check=True)
            time.sleep(5)
            
            # Kill any remaining processes
            try:
                subprocess.run(['pkill', '-f', 'gunicorn.*currency-exchange'], 
                             timeout=10, capture_output=True)
            except subprocess.TimeoutExpired:
                logger.warning("Force killing gunicorn processes")
                subprocess.run(['pkill', '-9', '-f', 'gunicorn.*currency-exchange'], 
                             capture_output=True)
            
            time.sleep(2)
            
            # Clean up any socket files
            socket_files = [
                '/tmp/gunicorn.sock',
                '/var/run/gunicorn/currency-exchange.sock'
            ]
            for sock_file in socket_files:
                if os.path.exists(sock_file):
                    os.remove(sock_file)
                    logger.info(f"Removed socket file: {sock_file}")
            
            # Start the service
            subprocess.run(['systemctl', 'start', self.service_name], check=True)
            time.sleep(10)
            
            # Verify the restart
            if self.check_service_status() and self.check_port_availability():
                logger.info("Service restarted successfully")
                self.recovery_attempts = 0
                return True
            else:
                logger.error("Service restart failed")
                return False
                
        except Exception as e:
            logger.error(f"Error during service restart: {e}")
            return False
    
    def perform_health_check(self):
        """Perform comprehensive health check"""
        logger.info("Performing health check...")
        
        issues = []
        
        # Check service status
        if not self.check_service_status():
            issues.append("Service not running")
        
        # Check port availability
        if not self.check_port_availability():
            issues.append("Port not responding")
        
        # Check for socket errors
        socket_errors = self.check_socket_errors()
        if socket_errors > self.max_socket_errors:
            issues.append(f"Too many socket errors: {socket_errors}")
        
        # Check process health
        if not self.check_process_health():
            issues.append("Process health issues")
        
        return issues
    
    def run_recovery_cycle(self):
        """Run a single recovery cycle"""
        issues = self.perform_health_check()
        
        if not issues:
            logger.info("Health check passed")
            return True
        
        logger.warning(f"Health check failed: {', '.join(issues)}")
        
        if self.recovery_attempts >= self.max_recovery_attempts:
            logger.error(f"Max recovery attempts ({self.max_recovery_attempts}) reached")
            return False
        
        self.recovery_attempts += 1
        logger.info(f"Starting recovery attempt {self.recovery_attempts}")
        
        return self.restart_service()
    
    def run_daemon(self):
        """Run the recovery manager as a daemon"""
        logger.info("Starting socket recovery daemon...")
        
        while True:
            try:
                self.run_recovery_cycle()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error in recovery cycle: {e}")
                time.sleep(self.check_interval)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        # Run as daemon
        recovery_manager = SocketRecoveryManager()
        recovery_manager.run_daemon()
    else:
        # Run single check
        recovery_manager = SocketRecoveryManager()
        success = recovery_manager.run_recovery_cycle()
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()