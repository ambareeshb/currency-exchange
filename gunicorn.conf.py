# Gunicorn configuration for Currency Exchange Flask-SocketIO app
import multiprocessing
import os
import socket
import logging

# Enhanced logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server socket with enhanced error handling
bind = "127.0.0.1:5001"
backlog = 2048

# Worker processes - optimized for socket stability
workers = 1  # SocketIO requires single worker with eventlet
worker_class = "eventlet"
worker_connections = 1000  # Increased for better handling
timeout = 120  # Increased timeout for WebSocket connections
keepalive = 5  # Longer keepalive for WebSocket stability

# Enhanced restart settings for socket error recovery
max_requests = 1000  # Less frequent worker restarts for WebSocket stability
max_requests_jitter = 100
preload_app = True

# Logging with enhanced error tracking and fallback
import os
import sys

def setup_logging():
    """Setup logging with proper fallback handling"""
    log_dir = "/var/log/gunicorn"
    
    # Try to create log directory if it doesn't exist
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, mode=0o755, exist_ok=True)
            # Try to change ownership to ec2-user if running as root
            try:
                import pwd
                import grp
                ec2_user = pwd.getpwnam('ec2-user')
                os.chown(log_dir, ec2_user.pw_uid, ec2_user.pw_gid)
            except (KeyError, PermissionError, OSError):
                pass  # Ignore if we can't change ownership
    except (PermissionError, OSError) as e:
        print(f"Warning: Could not create log directory {log_dir}: {e}", file=sys.stderr)
    
    # Check if we can write to the log directory
    if os.path.exists(log_dir) and os.access(log_dir, os.W_OK):
        access_log_path = os.path.join(log_dir, "access.log")
        error_log_path = os.path.join(log_dir, "error.log")
        
        # Try to create log files if they don't exist
        try:
            for log_file in [access_log_path, error_log_path]:
                if not os.path.exists(log_file):
                    with open(log_file, 'a'):
                        pass
                    # Try to change ownership
                    try:
                        import pwd
                        ec2_user = pwd.getpwnam('ec2-user')
                        os.chown(log_file, ec2_user.pw_uid, ec2_user.pw_gid)
                    except (KeyError, PermissionError, OSError):
                        pass
            
            return access_log_path, error_log_path
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not create log files: {e}", file=sys.stderr)
    
    # Fallback to systemd journal/stdout/stderr
    print("Falling back to stdout/stderr logging", file=sys.stderr)
    return "-", "-"

# Setup logging
accesslog, errorlog = setup_logging()
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s %(p)s'

# Process naming
proc_name = "currency-exchange"

# Server mechanics with enhanced error handling
daemon = False
pidfile = "/var/run/gunicorn/currency-exchange.pid"
user = "ec2-user"
group = "ec2-user"
tmp_upload_dir = None

# Enhanced socket options to prevent "Bad file descriptor" errors
def when_ready(server):
    """Configure socket options when server is ready"""
    server.log.info("Server is ready. Configuring socket options...")
    
    # Configure socket options for better error handling
    for sock in server.LISTENERS:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # Set TCP keepalive options if available
        if hasattr(socket, 'TCP_KEEPIDLE'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        if hasattr(socket, 'TCP_KEEPINTVL'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        if hasattr(socket, 'TCP_KEEPCNT'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    
    server.log.info("Socket options configured successfully")

def worker_int(worker):
    """Handle worker interrupt signals gracefully"""
    worker.log.info("Worker received INT or QUIT signal, shutting down gracefully...")
    try:
        # Close any open connections gracefully
        import eventlet
        eventlet.sleep(0.1)  # Allow pending operations to complete
    except Exception as e:
        worker.log.error(f"Error during worker shutdown: {e}")

def pre_fork(server, worker):
    """Pre-fork hook with enhanced logging"""
    server.log.info("Worker spawning (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Post-fork hook with socket error prevention"""
    worker.log.info("Worker spawned (pid: %s)", worker.pid)
    
    # Configure worker-specific socket handling
    try:
        import signal
        import sys
        
        def handle_broken_pipe(signum, frame):
            worker.log.warning("Broken pipe detected, ignoring...")
            
        signal.signal(signal.SIGPIPE, handle_broken_pipe)
        
    except Exception as e:
        worker.log.error(f"Error configuring worker signal handlers: {e}")

def post_worker_init(worker):
    """Enhanced worker initialization"""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)
    
    # Set up enhanced error handling in the worker
    try:
        import eventlet
        # Configure eventlet for better socket handling
        eventlet.monkey_patch(socket=True, select=True)
        
        # Set up socket error recovery
        original_socket = socket.socket
        
        def enhanced_socket(*args, **kwargs):
            sock = original_socket(*args, **kwargs)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except Exception as e:
                worker.log.warning(f"Could not set socket options: {e}")
            return sock
            
        socket.socket = enhanced_socket
        
    except Exception as e:
        worker.log.error(f"Error in worker initialization: {e}")

def worker_abort(worker):
    """Enhanced worker abort handling"""
    worker.log.warning("Worker aborted (pid: %s), cleaning up...", worker.pid)
    try:
        # Cleanup any resources
        import gc
        gc.collect()
    except Exception as e:
        worker.log.error(f"Error during worker cleanup: {e}")

# Enhanced error handling
def on_exit(server):
    """Enhanced server shutdown"""
    server.log.info("Server is shutting down, cleaning up resources...")
    try:
        # Close all listeners gracefully
        for sock in server.LISTENERS:
            try:
                sock.close()
            except Exception as e:
                server.log.warning(f"Error closing socket: {e}")
    except Exception as e:
        server.log.error(f"Error during server shutdown: {e}")

# Environment variables
raw_env = [
    'FLASK_ENV=production',
    'DEBUG=false'
]

# Enhanced graceful timeout for worker shutdown
graceful_timeout = 30  # Longer timeout for WebSocket connections

# Enable SO_REUSEPORT for better performance and error recovery
reuse_port = True

# Enhanced request handling
disable_redirect_access_to_syslog = True
capture_output = True

# Additional socket error prevention settings
worker_tmp_dir = "/dev/shm"  # Use shared memory for better performance
max_worker_memory = 200  # MB - restart worker if memory exceeds this
worker_timeout = 30  # Worker timeout for hanging requests