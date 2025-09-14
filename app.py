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

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/currency-exchange/app.log') if os.path.exists('/var/log/currency-exchange') else logging.StreamHandler(sys.stdout)
    ]
)

# Add socket error filter to all loggers
socket_filter = SocketErrorFilter()
logging.getLogger().addFilter(socket_filter)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///currency_exchange.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Flask logging with socket error handling
app.logger.setLevel(logging.INFO)
app.logger.addFilter(socket_filter)

db = SQLAlchemy(app)

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

# Error handlers
@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Server Error: {error}')
    db.session.rollback()
    return render_template('base.html'), 500

@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'Page not found: {request.url}')
    return render_template('base.html'), 404

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
    admin_user = AdminUser.query.filter_by(username=user_id).first()
    if admin_user:
        return User(admin_user.username)
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
    currencies_db = Currency.query.order_by(Currency.symbol.asc()).all()
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
    
    db.session.commit()
    
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
    
    db.session.delete(currency)
    db.session.commit()
    
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
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        
        # Test basic app functionality
        currency_count = Currency.query.count()
        
        return {
            'status': 'healthy',
            'timestamp': db.func.current_timestamp(),
            'database': 'connected',
            'currencies': currency_count,
            'version': '1.0.0'
        }, 200
    except Exception as e:
        app.logger.error(f'Health check failed: {e}')
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': db.func.current_timestamp()
        }, 503

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
        # Initialize database and run migrations
        init_db_and_migrations()
        
        # Get configuration from environment
        port = int(os.environ.get('PORT', 5001))
        debug = os.environ.get('DEBUG', 'false').lower() == 'true'
        
        app.logger.info(f'Starting Currency Exchange app on port {port}')
        socketio.run(app, debug=debug, port=port, host='0.0.0.0')
    except Exception as e:
        app.logger.error(f'Failed to start application: {e}')
        sys.exit(1)