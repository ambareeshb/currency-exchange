# Gunicorn configuration for Currency Exchange Flask app
import multiprocessing
import os
import socket
import logging

# Server socket
bind = f"127.0.0.1:{os.environ.get('PORT', '5001')}"
backlog = 2048

# Worker processes - simplified for standard Flask app
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart settings
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Systemd journal logging configuration
# Use stdout/stderr which systemd will capture to journal
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "currency-exchange"

# Server mechanics
daemon = False
# Remove pidfile for systemd managed service - not needed
# pidfile = "/var/run/gunicorn/currency-exchange.pid"
# User and group should be set via systemd service, not hardcoded here
# user = "ec2-user"
# group = "ec2-user"
tmp_upload_dir = None

# Socket options
def when_ready(server):
    """Configure socket options when server is ready"""
    server.log.info("Server is ready. Configuring socket options...")
    
    for sock in server.LISTENERS:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    server.log.info("Socket options configured successfully")

def worker_int(worker):
    """Handle worker interrupt signals gracefully"""
    worker.log.info("Worker received INT or QUIT signal, shutting down gracefully...")

def pre_fork(server, worker):
    """Pre-fork hook"""
    server.log.info("Worker spawning (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Post-fork hook"""
    worker.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    """Worker initialization"""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    """Worker abort handling"""
    worker.log.warning("Worker aborted (pid: %s)", worker.pid)

def on_exit(server):
    """Server shutdown"""
    server.log.info("Server is shutting down...")

# Environment variables
raw_env = [
    'FLASK_ENV=production',
    'DEBUG=false'
]

# Graceful timeout
graceful_timeout = 30

# Enable SO_REUSEPORT
reuse_port = True

# Systemd journal integration
# Disable file-based logging redirects
disable_redirect_access_to_syslog = False
capture_output = True

# Performance settings
worker_tmp_dir = "/dev/shm"
max_worker_memory = 200  # MB
worker_timeout = 30