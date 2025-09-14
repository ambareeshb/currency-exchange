from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from werkzeug.security import check_password_hash, generate_password_hash
import os
import logging
import signal
import sys
import socket
import errno
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enhanced logging configuration with socket error tracking
class SocketErrorFilter(logging.Filter):
    """Filter to track and handle socket-related errors"""
    def filter(self, record):
        # Log socket errors but don't let them crash the app
        if hasattr(record, 'msg') and 'Bad file descriptor' in str(record.msg):
            record.msg = f"[SOCKET_ERROR_HANDLED] {record.msg}"
        return True

# Configure enhanced logging with proper fallback
def setup_logging():
    """Setup logging with proper file and console handlers"""
    log_format = '%(asctime)s %(levelname)s %(name)s %(message)s'
    
    # Always add console handler
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Try to add file handler if directory exists
    log_dir = '/var/log/currency-exchange'
    if os.path.exists(log_dir):
        try:
            handlers.append(logging.FileHandler(os.path.join(log_dir, 'app.log')))
            print(f"Logging to file: {os.path.join(log_dir, 'app.log')}")
        except (OSError, PermissionError) as e:
            print(f"Could not create log file: {e}")
    else:
        # Create local log file as fallback
        try:
            handlers.append(logging.FileHandler('app.log'))
            print("Logging to local file: app.log")
        except (OSError, PermissionError) as e:
            print(f"Could not create local log file: {e}")
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers,
        force=True  # Override any existing configuration
    )

# Setup logging
setup_logging()

# Add socket error filter to all loggers
socket_filter = SocketErrorFilter()
logging.getLogger().addFilter(socket_filter)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///currency_exchange.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enhanced SQLAlchemy configuration to prevent threading issues
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Verify connections before use
    'pool_recycle': 300,    # Recycle connections every 5 minutes
    'pool_timeout': 20,     # Timeout for getting connection from pool
    'max_overflow': 0,      # Don't allow overflow connections
    'echo': False,          # Set to True for SQL debugging
    # Critical threading fixes
    'pool_reset_on_return': 'commit',  # Reset connections on return
    'pool_size': 5,         # Limit pool size to prevent contention
    # Threading-safe connection handling
    'connect_args': {
        'check_same_thread': False,  # For SQLite threading safety
        'timeout': 20  # Database timeout
    } if 'sqlite' in os.environ.get('DATABASE_URL', 'sqlite:///currency_exchange.db') else {
        'connect_timeout': 20,
        'pool_timeout': 20
    }
}

# Configure Flask logging with socket error handling
app.logger.setLevel(logging.INFO)
app.logger.addFilter(socket_filter)

db = SQLAlchemy(app)

# Enhanced database session handling for threading safety
@app.teardown_appcontext
def close_db_session(error):
    """Ensure database sessions are properly closed after each request"""
    try:
        # Force rollback any pending transactions
        if db.session.is_active:
            db.session.rollback()
        # Remove the session from the registry
        db.session.remove()
    except Exception as e:
        app.logger.warning(f"Error closing database session: {e}")
        # Force cleanup even if there's an error
        try:
            db.session.close()
        except:
            pass

# Database connection health check
def check_db_connection():
    """Check if database connection is healthy"""
    try:
        db.session.execute('SELECT 1')
        return True
    except Exception as e:
        app.logger.error(f"Database connection check failed: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False

# Connection pool recovery function
def recover_db_pool():
    """Recover database connection pool from threading issues"""
    try:
        app.logger.info("Attempting to recover database connection pool...")
        
        # Force close all connections in the pool
        db.engine.dispose()
        
        # Clear any pending sessions
        db.session.remove()
        
        # Test new connection
        with db.engine.connect() as conn:
            conn.execute('SELECT 1')
        
        app.logger.info("Database connection pool recovered successfully")
        return True
    except Exception as e:
        app.logger.error(f"Failed to recover database pool: {e}")
        return False

# Enhanced database operation wrapper
def safe_db_operation(operation_func, *args, **kwargs):
    """Safely execute database operations with automatic recovery"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            if 'cannot notify on un-acquired lock' in error_msg or 'bad file descriptor' in error_msg:
                app.logger.warning(f"Database threading issue detected (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Try to recover the pool
                    recover_db_pool()
                    continue
            raise e
    raise Exception(f"Failed after {max_retries} attempts")

# Enhanced SocketIO configuration with better error handling
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    logger=False,  # Reduce logging noise
    engineio_logger=False,  # Reduce logging noise
    # Enhanced configuration for socket stability
    ping_timeout=30,  # Reduced timeout
    ping_interval=10,  # More frequent pings
    max_http_buffer_size=1000000,
    allow_upgrades=True,
    transports=['polling', 'websocket'],  # Prefer polling first
    # Additional stability settings
    manage_session=False  # Let Flask-Login handle sessions
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Enhanced Error handlers with detailed logging
@app.errorhandler(500)
def internal_error(error):
    import traceback
    error_details = {
        'error': str(error),
        'url': request.url,
        'method': request.method,
        'remote_addr': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'traceback': traceback.format_exc()
    }
    app.logger.error(f'Internal Server Error (500): {error_details}')
    print(f"INTERNAL SERVER ERROR: {error_details}")  # Ensure it's visible in console
    
    # Enhanced database session cleanup
    try:
        db.session.rollback()
        db.session.remove()
    except Exception as cleanup_error:
        app.logger.error(f'Error during database cleanup: {cleanup_error}')
    
    return render_template('base.html'), 500

@app.errorhandler(404)
def not_found_error(error):
    error_details = {
        'url': request.url,
        'method': request.method,
        'remote_addr': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown')
    }
    app.logger.warning(f'Page not found (404): {error_details}')
    return render_template('base.html'), 404

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    error_details = {
        'error': str(e),
        'type': type(e).__name__,
        'url': request.url,
        'method': request.method,
        'remote_addr': request.remote_addr,
        'traceback': traceback.format_exc()
    }
    app.logger.error(f'Unhandled Exception: {error_details}')
    print(f"UNHANDLED EXCEPTION: {error_details}")  # Ensure it's visible in console
    
    # Enhanced database session cleanup for threading issues
    try:
        db.session.rollback()
        db.session.remove()
    except Exception as cleanup_error:
        app.logger.error(f'Error during database cleanup: {cleanup_error}')
        # Try pool recovery if it's a threading issue
        if 'cannot notify on un-acquired lock' in str(cleanup_error):
            recover_db_pool()
    
    return render_template('base.html'), 500

# Signal handlers for graceful shutdown
def signal_handler(sig, frame):
    app.logger.info('Received shutdown signal, cleaning up...')
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<AdminUser {self.username}>'

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    """Thread-safe user loader with proper session management"""
    def _load_user():
        admin_user = AdminUser.query.filter_by(username=user_id).first()
        if admin_user:
            return User(admin_user.username)
        return None
    
    try:
        return safe_db_operation(_load_user)
    except Exception as e:
        app.logger.error(f"Error loading user {user_id}: {e}")
        # Clean up the session on error
        try:
            db.session.rollback()
            db.session.remove()
        except:
            pass
        return None

class Currency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(10), nullable=False, unique=True)
    # Buying rate range (exchange buys currency from customer)
    min_buying_rate_to_aed = db.Column(db.Float, nullable=True)  # Minimum buying rate
    max_buying_rate_to_aed = db.Column(db.Float, nullable=True)  # Maximum buying rate
    # Selling rate range (exchange sells currency to customer)
    min_selling_rate_to_aed = db.Column(db.Float, nullable=True)  # Minimum selling rate
    max_selling_rate_to_aed = db.Column(db.Float, nullable=True)  # Maximum selling rate
    admin_notes = db.Column(db.Text, nullable=True)  # Admin notes about this currency
    
    def __repr__(self):
        return f'<Currency {self.symbol}: {self.name}>'
    
    @property
    def has_buying_range(self):
        """Check if currency has buying rate range defined"""
        return self.min_buying_rate_to_aed is not None and self.max_buying_rate_to_aed is not None
    
    @property
    def has_selling_range(self):
        """Check if currency has selling rate range defined"""
        return self.min_selling_rate_to_aed is not None and self.max_selling_rate_to_aed is not None
    
    @property
    def has_exchange_rates(self):
        """Check if currency has any exchange rates defined"""
        return self.has_buying_range or self.has_selling_range
    
    @property
    def buying_rate_display(self):
        """Get formatted buying rate range for display"""
        if self.has_buying_range:
            return f"{self.min_buying_rate_to_aed:.6f} - {self.max_buying_rate_to_aed:.6f}"
        return "Not set"
    
    @property
    def selling_rate_display(self):
        """Get formatted selling rate range for display"""
        if self.has_selling_range:
            return f"{self.min_selling_rate_to_aed:.6f} - {self.max_selling_rate_to_aed:.6f}"
        return "Not set"
    
    @property
    def buying_from_aed_display(self):
        """Get AED to currency rate range when exchange buys (customer sells AED)"""
        if self.has_selling_range:
            # When customer sells AED, they get foreign currency at selling rate (inverted)
            min_rate = 1 / self.max_selling_rate_to_aed
            max_rate = 1 / self.min_selling_rate_to_aed
            return f"{min_rate:.6f} - {max_rate:.6f}"
        return "Not set"
    
    @property
    def selling_from_aed_display(self):
        """Get AED to currency rate range when exchange sells (customer buys AED)"""
        if self.has_buying_range:
            # When customer buys AED, they pay foreign currency at buying rate (inverted)
            min_rate = 1 / self.max_buying_rate_to_aed
            max_rate = 1 / self.min_buying_rate_to_aed
            return f"{min_rate:.6f} - {max_rate:.6f}"
        return "Not set"

@app.route('/')
def index():
    def _get_currencies():
        return Currency.query.order_by(Currency.symbol.asc()).all()
    
    currencies_db = safe_db_operation(_get_currencies)
    currencies = [
        {
            'id': c.id,
            'name': c.name,
            'symbol': c.symbol,
            'min_buying_rate_to_aed': c.min_buying_rate_to_aed,
            'max_buying_rate_to_aed': c.max_buying_rate_to_aed,
            'min_selling_rate_to_aed': c.min_selling_rate_to_aed,
            'max_selling_rate_to_aed': c.max_selling_rate_to_aed,
            'admin_notes': c.admin_notes,
            'has_exchange_rates': c.has_exchange_rates,
            'has_buying_range': c.has_buying_range,
            'has_selling_range': c.has_selling_range,
            'buying_rate_display': c.buying_rate_display,
            'selling_rate_display': c.selling_rate_display,
            'buying_from_aed_display': c.buying_from_aed_display,
            'selling_from_aed_display': c.selling_from_aed_display
        }
        for c in currencies_db
    ]
    return render_template('public_rates.html', currencies=currencies, currencies_db=currencies_db)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        admin_user = AdminUser.query.filter_by(username=username).first()
        
        if admin_user and admin_user.check_password(password):
            user = User(admin_user.username)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    currencies = Currency.query.order_by(Currency.symbol.asc()).all()
    return render_template('dashboard.html', currencies=currencies)

@app.route('/add_currency', methods=['POST'])
@login_required
def add_currency():
    name = request.form['name']
    symbol = request.form['symbol'].upper()
    admin_notes = request.form.get('admin_notes', '').strip()
    
    # Handle buying rate range
    min_buying_rate = None
    max_buying_rate = None
    if request.form.get('min_buying_rate_to_aed') and request.form.get('max_buying_rate_to_aed'):
        min_buying_rate = float(request.form['min_buying_rate_to_aed'])
        max_buying_rate = float(request.form['max_buying_rate_to_aed'])
        
        # Validate buying range
        if min_buying_rate >= max_buying_rate:
            flash('Minimum buying rate must be less than maximum buying rate', 'error')
            return redirect(url_for('dashboard'))
    
    # Handle selling rate range
    min_selling_rate = None
    max_selling_rate = None
    if request.form.get('min_selling_rate_to_aed') and request.form.get('max_selling_rate_to_aed'):
        min_selling_rate = float(request.form['min_selling_rate_to_aed'])
        max_selling_rate = float(request.form['max_selling_rate_to_aed'])
        
        # Validate selling range
        if min_selling_rate >= max_selling_rate:
            flash('Minimum selling rate must be less than maximum selling rate', 'error')
            return redirect(url_for('dashboard'))
    
    # Validate that buying rates are lower than selling rates
    if min_buying_rate and min_selling_rate and max_buying_rate >= min_selling_rate:
        flash('Buying rates must be lower than selling rates', 'error')
        return redirect(url_for('dashboard'))
    
    # Check if currency symbol already exists
    existing = Currency.query.filter_by(symbol=symbol).first()
    if existing:
        flash(f'Currency with symbol {symbol} already exists', 'error')
        return redirect(url_for('dashboard'))
    
    currency = Currency(
        name=name,
        symbol=symbol,
        min_buying_rate_to_aed=min_buying_rate,
        max_buying_rate_to_aed=max_buying_rate,
        min_selling_rate_to_aed=min_selling_rate,
        max_selling_rate_to_aed=max_selling_rate,
        admin_notes=admin_notes if admin_notes else None
    )
    db.session.add(currency)
    db.session.commit()
    
    # Emit real-time update to all connected clients with error handling
    safe_emit('currency_added', {
        'id': currency.id,
        'name': currency.name,
        'symbol': currency.symbol,
        'min_buying_rate_to_aed': currency.min_buying_rate_to_aed,
        'max_buying_rate_to_aed': currency.max_buying_rate_to_aed,
        'min_selling_rate_to_aed': currency.min_selling_rate_to_aed,
        'max_selling_rate_to_aed': currency.max_selling_rate_to_aed,
        'admin_notes': currency.admin_notes,
        'has_exchange_rates': currency.has_exchange_rates,
        'has_buying_range': currency.has_buying_range,
        'has_selling_range': currency.has_selling_range,
        'buying_rate_display': currency.buying_rate_display,
        'selling_rate_display': currency.selling_rate_display,
        'buying_from_aed_display': currency.buying_from_aed_display,
        'selling_from_aed_display': currency.selling_from_aed_display
    })
    
    flash(f'Currency {symbol} added successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_currency/<int:currency_id>', methods=['POST'])
@login_required
def update_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    currency.name = request.form['name']
    currency.admin_notes = request.form.get('admin_notes', '').strip() or None
    
    # Handle buying rate range
    if request.form.get('min_buying_rate_to_aed') and request.form.get('max_buying_rate_to_aed'):
        min_buying_rate = float(request.form['min_buying_rate_to_aed'])
        max_buying_rate = float(request.form['max_buying_rate_to_aed'])
        
        # Validate buying range
        if min_buying_rate >= max_buying_rate:
            flash('Minimum buying rate must be less than maximum buying rate', 'error')
            return redirect(url_for('dashboard'))
            
        currency.min_buying_rate_to_aed = min_buying_rate
        currency.max_buying_rate_to_aed = max_buying_rate
    else:
        currency.min_buying_rate_to_aed = None
        currency.max_buying_rate_to_aed = None
    
    # Handle selling rate range
    if request.form.get('min_selling_rate_to_aed') and request.form.get('max_selling_rate_to_aed'):
        min_selling_rate = float(request.form['min_selling_rate_to_aed'])
        max_selling_rate = float(request.form['max_selling_rate_to_aed'])
        
        # Validate selling range
        if min_selling_rate >= max_selling_rate:
            flash('Minimum selling rate must be less than maximum selling rate', 'error')
            return redirect(url_for('dashboard'))
            
        currency.min_selling_rate_to_aed = min_selling_rate
        currency.max_selling_rate_to_aed = max_selling_rate
    else:
        currency.min_selling_rate_to_aed = None
        currency.max_selling_rate_to_aed = None
    
    # Validate that buying rates are lower than selling rates
    if (currency.min_buying_rate_to_aed and currency.min_selling_rate_to_aed and
        currency.max_buying_rate_to_aed >= currency.min_selling_rate_to_aed):
        flash('Buying rates must be lower than selling rates', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        db.session.remove()
        app.logger.error(f'Database error updating currency: {e}')
        raise
    
    # Emit real-time update to all connected clients with error handling
    safe_emit('currency_updated', {
        'id': currency.id,
        'name': currency.name,
        'symbol': currency.symbol,
        'min_buying_rate_to_aed': currency.min_buying_rate_to_aed,
        'max_buying_rate_to_aed': currency.max_buying_rate_to_aed,
        'min_selling_rate_to_aed': currency.min_selling_rate_to_aed,
        'max_selling_rate_to_aed': currency.max_selling_rate_to_aed,
        'admin_notes': currency.admin_notes,
        'has_exchange_rates': currency.has_exchange_rates,
        'has_buying_range': currency.has_buying_range,
        'has_selling_range': currency.has_selling_range,
        'buying_rate_display': currency.buying_rate_display,
        'selling_rate_display': currency.selling_rate_display,
        'buying_from_aed_display': currency.buying_from_aed_display,
        'selling_from_aed_display': currency.selling_from_aed_display
    })
    
    flash(f'Currency {currency.symbol} updated successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_currency/<int:currency_id>', methods=['POST'])
@login_required
def delete_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    symbol = currency.symbol
    currency_data = {
        'id': currency.id,
        'symbol': currency.symbol
    }
    
    try:
        db.session.delete(currency)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        db.session.remove()
        app.logger.error(f'Database error deleting currency: {e}')
        raise
    
    # Emit real-time update to all connected clients with error handling
    safe_emit('currency_deleted', currency_data)
    
    flash(f'Currency {symbol} deleted successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/from_aed')
@login_required
def from_aed():
    currencies = Currency.query.order_by(Currency.symbol.asc()).all()
    return render_template('from_aed.html', currencies=currencies)

@app.route('/to_aed')
@login_required
def to_aed():
    currencies = Currency.query.order_by(Currency.symbol.asc()).all()
    return render_template('to_aed.html', currencies=currencies)

@app.route('/currency_notes/<int:currency_id>')
def get_currency_notes(currency_id):
    """Get currency notes for info button"""
    currency = Currency.query.get_or_404(currency_id)
    return {
        'id': currency.id,
        'symbol': currency.symbol,
        'name': currency.name,
        'notes': currency.admin_notes or 'No notes available for this currency.',
        'has_exchange_rates': currency.has_exchange_rates,
        'buying_rate_display': currency.buying_rate_display,
        'selling_rate_display': currency.selling_rate_display,
        'buying_rate_display': currency.buying_rate_display,
        'selling_rate_display': currency.selling_rate_display,
        'buying_from_aed_display': currency.buying_from_aed_display,
        'selling_from_aed_display': currency.selling_from_aed_display
    }

@app.route('/admin')
def admin_redirect():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/health')
def health_check():
    """Enhanced health check endpoint for monitoring"""
    health_status = {
        'status': 'healthy',
        'timestamp': None,
        'database': 'unknown',
        'currencies': 0,
        'version': '1.0.0',
        'checks': {}
    }
    
    try:
        # Test database connection with timeout
        import time
        start_time = time.time()
        
        # Basic connection test
        db.session.execute('SELECT 1')
        connection_time = time.time() - start_time
        health_status['checks']['database_connection'] = {
            'status': 'ok',
            'response_time_ms': round(connection_time * 1000, 2)
        }
        
        # Test database queries
        try:
            currency_count = Currency.query.count()
            health_status['currencies'] = currency_count
            health_status['checks']['database_queries'] = {'status': 'ok'}
        except Exception as query_error:
            health_status['checks']['database_queries'] = {
                'status': 'error',
                'error': str(query_error)
            }
            raise query_error
        
        # Test database session health
        try:
            db.session.commit()
            health_status['checks']['database_session'] = {'status': 'ok'}
        except Exception as session_error:
            health_status['checks']['database_session'] = {
                'status': 'error',
                'error': str(session_error)
            }
            # Try to recover the session
            try:
                db.session.rollback()
                db.session.remove()
            except:
                pass
            raise session_error
        
        health_status['database'] = 'connected'
        health_status['timestamp'] = time.time()
        
        return health_status, 200
        
    except Exception as e:
        app.logger.error(f'Health check failed: {e}')
        health_status.update({
            'status': 'unhealthy',
            'error': str(e),
            'error_type': type(e).__name__,
            'timestamp': time.time()
        })
        
        # Attempt database cleanup
        try:
            db.session.rollback()
            db.session.remove()
        except Exception as cleanup_error:
            health_status['cleanup_error'] = str(cleanup_error)
        
        return health_status, 503

def init_db_and_migrations():
    """Initialize database and run migrations"""
    from migrations import run_migrations
    run_migrations()

# Enhanced SocketIO error handlers with socket error recovery
@socketio.on_error_default
def default_error_handler(e):
    """Enhanced default error handler for SocketIO"""
    error_msg = str(e)
    
    # Handle specific socket errors gracefully
    if 'Bad file descriptor' in error_msg:
        app.logger.warning(f'Socket descriptor error handled gracefully: {error_msg}')
        # Don't propagate the error, just log it
        return False
    elif 'Connection reset by peer' in error_msg:
        app.logger.warning(f'Client connection reset: {error_msg}')
        return False
    elif 'Broken pipe' in error_msg:
        app.logger.warning(f'Broken pipe handled: {error_msg}')
        return False
    else:
        app.logger.error(f'SocketIO error: {error_msg}')
        return True

@socketio.on('connect')
def on_connect():
    """Enhanced connect handler with error recovery"""
    try:
        app.logger.info(f'Client connected: {request.sid}')
        # Send a welcome message to confirm connection
        emit('connection_confirmed', {'status': 'connected', 'sid': request.sid})
    except Exception as e:
        app.logger.warning(f'Error in connect handler: {e}')

@socketio.on('disconnect')
def on_disconnect():
    """Enhanced disconnect handler with graceful cleanup"""
    try:
        app.logger.info(f'Client disconnected: {request.sid}')
    except Exception as e:
        app.logger.warning(f'Error in disconnect handler: {e}')

@socketio.on_error()
def error_handler(e):
    """Namespace-specific error handler"""
    app.logger.warning(f'SocketIO namespace error: {e}')

# Enhanced socket error recovery functions
def handle_socket_error(func):
    """Decorator to handle socket errors in SocketIO emissions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (OSError, socket.error) as e:
            if e.errno == errno.EBADF:  # Bad file descriptor
                app.logger.warning(f'Bad file descriptor in {func.__name__}, skipping emission')
                return None
            elif e.errno == errno.EPIPE:  # Broken pipe
                app.logger.warning(f'Broken pipe in {func.__name__}, skipping emission')
                return None
            elif e.errno == errno.ECONNRESET:  # Connection reset
                app.logger.warning(f'Connection reset in {func.__name__}, skipping emission')
                return None
            else:
                app.logger.error(f'Socket error in {func.__name__}: {e}')
                raise
        except Exception as e:
            app.logger.error(f'Unexpected error in {func.__name__}: {e}')
            raise
    return wrapper

# Enhanced emission functions with error handling
@handle_socket_error
def safe_emit(event, data, **kwargs):
    """Safely emit SocketIO events with error handling"""
    try:
        socketio.emit(event, data, **kwargs)
        app.logger.debug(f'Successfully emitted {event}')
    except Exception as e:
        app.logger.warning(f'Failed to emit {event}: {e}')

if __name__ == '__main__':
    try:
        print("=" * 50)
        print("STARTING CURRENCY EXCHANGE APPLICATION")
        print("=" * 50)
        
        # Initialize database and run migrations
        print("Initializing database and running migrations...")
        init_db_and_migrations()
        print("Database initialization completed.")
        
        # Get configuration from environment
        port = int(os.environ.get('PORT', 5001))
        debug = os.environ.get('DEBUG', 'false').lower() == 'true'
        
        startup_info = {
            'port': port,
            'debug': debug,
            'host': '0.0.0.0',
            'python_version': sys.version,
            'working_directory': os.getcwd()
        }
        
        app.logger.info(f'Starting Currency Exchange app with config: {startup_info}')
        print(f"Starting server on port {port} (debug={debug})")
        print("Application startup completed successfully!")
        print("=" * 50)
        
        socketio.run(app, debug=debug, port=port, host='0.0.0.0')
    except Exception as e:
        import traceback
        error_msg = f'Failed to start application: {e}\nTraceback: {traceback.format_exc()}'
        app.logger.error(error_msg)
        print(f"STARTUP ERROR: {error_msg}")
        sys.exit(1)