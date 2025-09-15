from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Require SECRET_KEY in production - no fallback to insecure default
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise ValueError("SECRET_KEY environment variable must be set for production deployment")
app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///currency_exchange.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemy configuration for better stability
from sqlalchemy.pool import NullPool

database_url = os.environ.get('DATABASE_URL', 'sqlite:///currency_exchange.db')
is_sqlite = 'sqlite' in database_url

if is_sqlite:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'poolclass': NullPool,
        'pool_pre_ping': True,
        'connect_args': {
            'check_same_thread': False,
            'timeout': 60,
        },
        'echo': False
    }
else:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'poolclass': NullPool,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 60,
        },
        'echo': False
    }

db = SQLAlchemy(app)

@app.teardown_appcontext
def close_db_session(error):
    """Ensure database sessions are properly closed after each request"""
    try:
        if error:
            db.session.rollback()
        else:
            db.session.commit()
        db.session.remove()
    except Exception:
        try:
            db.session.remove()
        except Exception:
            pass

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    if not user_id:
        return None
    
    try:
        admin_user = AdminUser.query.filter_by(username=user_id).first()
        if admin_user:
            return User(admin_user.username)
        return None
    except Exception:
        return None

class Currency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(10), nullable=False, unique=True)
    min_buying_rate_to_aed = db.Column(db.Float, nullable=True)
    max_buying_rate_to_aed = db.Column(db.Float, nullable=True)
    min_selling_rate_to_aed = db.Column(db.Float, nullable=True)
    max_selling_rate_to_aed = db.Column(db.Float, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<Currency {self.symbol}: {self.name}>'
    
    @property
    def has_buying_range(self):
        return self.min_buying_rate_to_aed is not None and self.max_buying_rate_to_aed is not None
    
    @property
    def has_selling_range(self):
        return self.min_selling_rate_to_aed is not None and self.max_selling_rate_to_aed is not None
    
    @property
    def has_exchange_rates(self):
        return self.has_buying_range or self.has_selling_range
    
    @property
    def buying_rate_display(self):
        if self.has_buying_range:
            return f"{self.min_buying_rate_to_aed:.6f} - {self.max_buying_rate_to_aed:.6f}"
        return "Not set"
    
    @property
    def selling_rate_display(self):
        if self.has_selling_range:
            return f"{self.min_selling_rate_to_aed:.6f} - {self.max_selling_rate_to_aed:.6f}"
        return "Not set"
    
    @property
    def buying_from_aed_display(self):
        if self.has_selling_range:
            min_rate = 1 / self.max_selling_rate_to_aed
            max_rate = 1 / self.min_selling_rate_to_aed
            return f"{min_rate:.6f} - {max_rate:.6f}"
        return "Not set"
    
    @property
    def selling_from_aed_display(self):
        if self.has_buying_range:
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
    # Get form data from session if there was an error
    form_data = session.pop('form_data', {})
    return render_template('dashboard.html', currencies=currencies, form_data=form_data)

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
        
        if min_buying_rate >= max_buying_rate:
            flash('Minimum buying rate must be less than maximum buying rate', 'error')
            # Store form data in session for persistence
            session['form_data'] = {
                'name': name,
                'symbol': symbol,
                'min_buying_rate_to_aed': request.form.get('min_buying_rate_to_aed'),
                'max_buying_rate_to_aed': request.form.get('max_buying_rate_to_aed'),
                'min_selling_rate_to_aed': request.form.get('min_selling_rate_to_aed'),
                'max_selling_rate_to_aed': request.form.get('max_selling_rate_to_aed'),
                'admin_notes': admin_notes
            }
            return redirect(url_for('dashboard'))
    
    # Handle selling rate range
    min_selling_rate = None
    max_selling_rate = None
    if request.form.get('min_selling_rate_to_aed') and request.form.get('max_selling_rate_to_aed'):
        min_selling_rate = float(request.form['min_selling_rate_to_aed'])
        max_selling_rate = float(request.form['max_selling_rate_to_aed'])
        
        if min_selling_rate >= max_selling_rate:
            flash('Minimum selling rate must be less than maximum selling rate', 'error')
            # Store form data in session for persistence
            session['form_data'] = {
                'name': name,
                'symbol': symbol,
                'min_buying_rate_to_aed': request.form.get('min_buying_rate_to_aed'),
                'max_buying_rate_to_aed': request.form.get('max_buying_rate_to_aed'),
                'min_selling_rate_to_aed': request.form.get('min_selling_rate_to_aed'),
                'max_selling_rate_to_aed': request.form.get('max_selling_rate_to_aed'),
                'admin_notes': admin_notes
            }
            return redirect(url_for('dashboard'))
    
    # Remove strict validation - allow overlapping rates
    # Users can now set overlapping buying and selling rates if needed
    
    # Check if currency symbol already exists
    existing = Currency.query.filter_by(symbol=symbol).first()
    if existing:
        flash(f'Currency with symbol {symbol} already exists', 'error')
        # Store form data in session for persistence
        session['form_data'] = {
            'name': name,
            'symbol': symbol,
            'min_buying_rate_to_aed': request.form.get('min_buying_rate_to_aed'),
            'max_buying_rate_to_aed': request.form.get('max_buying_rate_to_aed'),
            'min_selling_rate_to_aed': request.form.get('min_selling_rate_to_aed'),
            'max_selling_rate_to_aed': request.form.get('max_selling_rate_to_aed'),
            'admin_notes': admin_notes
        }
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
        
        if min_selling_rate >= max_selling_rate:
            flash('Minimum selling rate must be less than maximum selling rate', 'error')
            return redirect(url_for('dashboard'))
            
        currency.min_selling_rate_to_aed = min_selling_rate
        currency.max_selling_rate_to_aed = max_selling_rate
    else:
        currency.min_selling_rate_to_aed = None
        currency.max_selling_rate_to_aed = None
    
    # Remove strict validation - allow overlapping rates
    # Users can now set overlapping buying and selling rates if needed
    
    db.session.commit()
    flash(f'Currency {currency.symbol} updated successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_currency/<int:currency_id>', methods=['POST'])
@login_required
def delete_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    symbol = currency.symbol
    
    db.session.delete(currency)
    db.session.commit()
    
    flash(f'Currency {symbol} deleted successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/buying')
def buying():
    currencies = Currency.query.order_by(Currency.symbol.asc()).all()
    return render_template('buying.html', currencies=currencies)

@app.route('/selling')
def selling():
    currencies = Currency.query.order_by(Currency.symbol.asc()).all()
    return render_template('selling.html', currencies=currencies)

@app.route('/currency_notes/<int:currency_id>')
def get_currency_notes(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    return {
        'id': currency.id,
        'symbol': currency.symbol,
        'name': currency.name,
        'notes': currency.admin_notes or 'No notes available for this currency.',
        'has_exchange_rates': currency.has_exchange_rates,
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
    try:
        currency_count = Currency.query.count()
        return {
            'status': 'healthy',
            'database': 'connected',
            'currencies': currency_count,
            'version': '1.0.0'
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 503

def init_db_and_migrations():
    from migrations import run_migrations, load_sample_data
    run_migrations()
    
    # Load sample data if in development mode
    if os.environ.get('LOAD_SAMPLE_DATA', 'false').lower() == 'true':
        with app.app_context():
            load_sample_data(Currency, db)

if __name__ == '__main__':
    print("Starting Currency Exchange Application...")
    
    # Initialize database and run migrations
    init_db_and_migrations()
    
    # Get configuration from environment
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    print(f"Starting server on port {port}")
    app.run(debug=debug, port=port, host='0.0.0.0')