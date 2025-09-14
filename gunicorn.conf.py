# Gunicorn configuration for Currency Exchange Flask-SocketIO app
import multiprocessing
import os

# Server socket
bind = "127.0.0.1:5001"
backlog = 2048

# Worker processes
workers = 1  # SocketIO requires single worker with eventlet
worker_class = "eventlet"
worker_connections = 1000
timeout = 120
keepalive = 5

# Restart workers
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Logging
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "currency-exchange"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn/currency-exchange.pid"
user = "ec2-user"
group = "ec2-user"
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Socket options to prevent "Bad file descriptor" errors
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)

# Error handling
def on_exit(server):
    server.log.info("Server is shutting down")

# Environment variables
raw_env = [
    'FLASK_ENV=production',
    'DEBUG=false'
]

# Graceful timeout for worker shutdown
graceful_timeout = 30

# Enable SO_REUSEPORT for better performance
reuse_port = True

# Disable request buffering for real-time applications
disable_redirect_access_to_syslog = True