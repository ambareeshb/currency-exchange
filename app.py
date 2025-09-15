from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
import io
from datetime import datetime, timezone
from dotenv import load_dotenv
from PIL import Image, ImageOps

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

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    notes_updated_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Currency {self.symbol}: {self.name}>'
    
    @property
    def has_notes(self):
        """Check if currency has any notes (text or images)"""
        return bool(self.admin_notes) or len(self.images) > 0
    
    @property
    def latest_note_timestamp(self):
        """Get the timestamp of the most recent note (text or image)"""
        timestamps = []
        
        # Add text note timestamp if exists
        if self.notes_updated_at:
            timestamps.append(self.notes_updated_at)
        
        # Add image timestamps
        for image in self.images:
            if image.uploaded_at:
                timestamps.append(image.uploaded_at)
        
        return max(timestamps) if timestamps else None
    
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

class NoteImage(db.Model):
    __tablename__ = 'note_images'
    
    id = db.Column(db.Integer, primary_key=True)
    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    mime_type = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    caption = db.Column(db.Text, nullable=True)  # Optional caption for the image
    
    # Relationship
    currency = db.relationship('Currency', backref=db.backref('images', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<NoteImage {self.original_filename} for {self.currency.symbol}>'

# Utility functions for image processing
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def compress_image(image_data, max_size_mb=10, quality=85):
    """
    Compress image without losing quality significantly
    Returns compressed image data as bytes
    """
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary (for JPEG compatibility)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Auto-orient image based on EXIF data
        image = ImageOps.exif_transpose(image)
        
        # Calculate target size to stay under max_size_mb
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # Start with original dimensions
        width, height = image.size
        
        # If image is already small enough, try with high quality first
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        
        # If still too large, progressively reduce dimensions
        while output.tell() > max_size_bytes and (width > 800 or height > 800):
            # Reduce dimensions by 10%
            width = int(width * 0.9)
            height = int(height * 0.9)
            
            # Resize image
            resized_image = image.resize((width, height), Image.Resampling.LANCZOS)
            
            # Save with current quality
            output = io.BytesIO()
            resized_image.save(output, format='JPEG', quality=quality, optimize=True)
        
        # If still too large, reduce quality
        while output.tell() > max_size_bytes and quality > 50:
            quality -= 5
            output = io.BytesIO()
            if width != image.size[0] or height != image.size[1]:
                resized_image = image.resize((width, height), Image.Resampling.LANCZOS)
                resized_image.save(output, format='JPEG', quality=quality, optimize=True)
            else:
                image.save(output, format='JPEG', quality=quality, optimize=True)
        
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        print(f"Error compressing image: {e}")
        return None

def save_uploaded_image(file, currency_id, caption=None):
    """
    Save uploaded image with compression
    Returns tuple (success, filename_or_error_message)
    """
    try:
        if not file or not allowed_file(file.filename):
            return False, "Invalid file type. Allowed types: PNG, JPG, JPEG, GIF, WEBP"
        
        # Read file data
        file_data = file.read()
        
        # Check file size (10MB limit)
        if len(file_data) > app.config['MAX_CONTENT_LENGTH']:
            return False, "File size exceeds 10MB limit"
        
        # Compress image
        compressed_data = compress_image(file_data)
        if compressed_data is None:
            return False, "Failed to process image"
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Save compressed image
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        
        # Save to database
        note_image = NoteImage(
            currency_id=currency_id,
            filename=unique_filename,
            original_filename=file.filename,
            file_size=len(compressed_data),
            mime_type=file.content_type or f'image/{file_extension}',
            caption=caption
        )
        db.session.add(note_image)
        db.session.commit()
        
        return True, unique_filename
        
    except Exception as e:
        print(f"Error saving image: {e}")
        return False, f"Error saving image: {str(e)}"

# Image handling routes
@app.route('/upload_image/<int:currency_id>', methods=['POST'])
@login_required
def upload_image(currency_id):
    """Upload an image for a currency's notes"""
    currency = Currency.query.get_or_404(currency_id)
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Get optional caption
    caption = request.form.get('caption', '').strip() or None
    
    success, result = save_uploaded_image(file, currency_id, caption)
    
    if success:
        return jsonify({
            'success': True,
            'filename': result,
            'message': 'Image uploaded successfully'
        })
    else:
        return jsonify({'success': False, 'error': result}), 400

@app.route('/upload_multiple_images/<int:currency_id>', methods=['POST'])
@login_required
def upload_multiple_images(currency_id):
    """Upload multiple images for a currency's notes"""
    currency = Currency.query.get_or_404(currency_id)
    
    if 'images' not in request.files:
        return jsonify({'success': False, 'error': 'No image files provided'}), 400
    
    files = request.files.getlist('images')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': 'No files selected'}), 400
    
    uploaded_files = []
    errors = []
    
    for i, file in enumerate(files):
        if file.filename == '':
            continue
            
        # Get caption for this specific image if provided
        caption_key = f'caption_{i}'
        caption = request.form.get(caption_key, '').strip() or None
        
        success, result = save_uploaded_image(file, currency_id, caption)
        
        if success:
            uploaded_files.append({
                'filename': result,
                'original_filename': file.filename,
                'caption': caption
            })
        else:
            errors.append(f"{file.filename}: {result}")
    
    if uploaded_files:
        message = f"Successfully uploaded {len(uploaded_files)} image(s)"
        if errors:
            message += f". {len(errors)} file(s) failed to upload."
        
        return jsonify({
            'success': True,
            'uploaded_files': uploaded_files,
            'errors': errors,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': f"All uploads failed: {'; '.join(errors)}"
        }), 400

@app.route('/delete_image/<int:image_id>', methods=['POST'])
@login_required
def delete_image(image_id):
    """Delete an uploaded image"""
    image = NoteImage.query.get_or_404(image_id)
    currency_id = image.currency_id
    
    try:
        # Delete file from filesystem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete from database
        db.session.delete(image)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Image deleted successfully',
            'currency_id': currency_id,
            'image_id': image_id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Error deleting image: {str(e)}'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded images"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
            'has_notes': c.has_notes,  # Now includes both text and image notes
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
        admin_notes=admin_notes if admin_notes else None,
        notes_updated_at=datetime.now(timezone.utc) if admin_notes else None
    )
    db.session.add(currency)
    db.session.commit()
    
    # Handle multiple image uploads if provided
    uploaded_images = 0
    image_errors = []
    
    if 'note_images' in request.files:
        files = request.files.getlist('note_images')
        
        for i, file in enumerate(files):
            if file and file.filename != '':
                # Get caption for this specific image if provided
                caption_key = f'caption_{i}'
                caption = request.form.get(caption_key, '').strip() or None
                
                success, result = save_uploaded_image(file, currency.id, caption)
                if success:
                    uploaded_images += 1
                else:
                    image_errors.append(f"{file.filename}: {result}")
    
    # Generate appropriate flash message
    if uploaded_images > 0:
        if image_errors:
            flash(f'Currency {symbol} added successfully with {uploaded_images} image(s). {len(image_errors)} image(s) failed to upload.', 'warning')
        else:
            flash(f'Currency {symbol} added successfully with {uploaded_images} image(s)', 'success')
    elif image_errors:
        flash(f'Currency {symbol} added but all image uploads failed: {"; ".join(image_errors)}', 'warning')
    else:
        flash(f'Currency {symbol} added successfully', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/update_currency/<int:currency_id>', methods=['POST'])
@login_required
def update_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    currency.name = request.form['name']
    
    # Get the new admin notes
    new_admin_notes = request.form.get('admin_notes', '').strip() or None
    
    # Check if notes have changed and update timestamp accordingly
    if new_admin_notes != currency.admin_notes:
        currency.admin_notes = new_admin_notes
        currency.notes_updated_at = datetime.now(timezone.utc) if new_admin_notes else None
    else:
        currency.admin_notes = new_admin_notes
    
    # Handle buying rate range
    if request.form.get('min_buying_rate_to_aed') and request.form.get('max_buying_rate_to_aed'):
        min_buying_rate = float(request.form['min_buying_rate_to_aed'])
        max_buying_rate = float(request.form['max_buying_rate_to_aed'])
        
        if min_buying_rate >= max_buying_rate:
            return jsonify({'success': False, 'error': 'Minimum buying rate must be less than maximum buying rate'})
            
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
            return jsonify({'success': False, 'error': 'Minimum selling rate must be less than maximum selling rate'})
            
        currency.min_selling_rate_to_aed = min_selling_rate
        currency.max_selling_rate_to_aed = max_selling_rate
    else:
        currency.min_selling_rate_to_aed = None
        currency.max_selling_rate_to_aed = None
    
    # Handle multiple image uploads if provided
    uploaded_images = 0
    image_errors = []
    
    if 'note_images' in request.files:
        files = request.files.getlist('note_images')
        
        for i, file in enumerate(files):
            if file and file.filename != '':
                # Get caption for this specific image if provided
                caption_key = f'caption_{i}'
                caption = request.form.get(caption_key, '').strip() or None
                
                success, result = save_uploaded_image(file, currency.id, caption)
                if success:
                    uploaded_images += 1
                else:
                    image_errors.append(f"{file.filename}: {result}")
    
    # Commit currency updates
    db.session.commit()
    
    # Prepare response message
    message = f'Currency {currency.symbol} updated successfully'
    if uploaded_images > 0:
        message += f' with {uploaded_images} new image(s)'
    
    # Check if this is an AJAX request
    if request.headers.get('Content-Type', '').startswith('multipart/form-data') and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON response for AJAX requests
        response_data = {
            'success': True,
            'message': message,
            'currency_id': currency_id,
            'uploaded_images': uploaded_images
        }
        
        if image_errors:
            response_data['image_errors'] = image_errors
            response_data['message'] += f'. {len(image_errors)} image(s) failed to upload.'
        
        return jsonify(response_data)
    else:
        # Traditional form submission - redirect with flash message
        if uploaded_images > 0:
            if image_errors:
                flash(f'{message}. {len(image_errors)} image(s) failed to upload.', 'warning')
            else:
                flash(message, 'success')
        elif image_errors:
            flash(f'Currency {currency.symbol} updated but all image uploads failed: {"; ".join(image_errors)}', 'warning')
        else:
            flash(message, 'success')
        
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
    
    # Get attached images with captions
    images_data = []
    for image in currency.images:
        images_data.append({
            'id': image.id,
            'filename': image.filename,
            'original_filename': image.original_filename,
            'file_size': image.file_size,
            'mime_type': image.mime_type,
            'caption': image.caption,
            'uploaded_at': image.uploaded_at.isoformat() + 'Z' if image.uploaded_at else None
        })
    
    # Sort images by upload date (newest first)
    images_data.sort(key=lambda x: x['uploaded_at'] or '', reverse=True)
    
    return {
        'id': currency.id,
        'symbol': currency.symbol,
        'name': currency.name,
        'notes': currency.admin_notes or ('No text notes available for this currency.' if not images_data else ''),
        'notes_updated_at': currency.notes_updated_at.isoformat() + 'Z' if currency.notes_updated_at else None,
        'has_notes': currency.has_notes,
        'latest_note_timestamp': currency.latest_note_timestamp.isoformat() + 'Z' if currency.latest_note_timestamp else None,
        'has_exchange_rates': currency.has_exchange_rates,
        'buying_rate_display': currency.buying_rate_display,
        'selling_rate_display': currency.selling_rate_display,
        'buying_from_aed_display': currency.buying_from_aed_display,
        'selling_from_aed_display': currency.selling_from_aed_display,
        'images': images_data
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