"""
Database migrations for Currency Exchange Admin App
"""
import os
from werkzeug.security import generate_password_hash
from sqlalchemy import text

def run_migrations():
    """Run all database migrations"""
    from app import app, db, AdminUser
    
    print(f"Database URL: {'Set' if os.environ.get('DATABASE_URL') else 'Not set'}")
    print(f"Admin Username: {os.environ.get('ADMIN_USERNAME', 'Not set')}")
    print(f"Admin Password: {'Set' if os.environ.get('ADMIN_PASSWORD') else 'Not set'}")
    
    with app.app_context():
        print("Running database migrations...")
        
        # Migration 001: Update password_hash column length
        migration_001_update_password_hash_length()
        
        # Migration 003: Add new currency fields
        print("Running migration 003: Add currency notes and rate range fields...")
        migration_003_add_currency_fields()
        
        # Migration 004: Remove old rate_to_aed column
        print("Running migration 004: Remove old rate_to_aed column...")
        migration_004_remove_old_rate_column()
        
        # Migration 005: Add note_images table for image attachments
        print("Running migration 005: Add note_images table...")
        migration_005_add_note_images_table()
        
        # Migration 006: Add caption column to note_images table
        print("Running migration 006: Add caption column to note_images...")
        migration_006_add_caption_to_note_images()
        
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        
        # Check what tables were created
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Tables created: {tables}")
        except Exception as e:
            print(f"Could not list tables: {e}")
        
        # Migration 002: Create admin user
        print("Running migration 002: Create admin user...")
        migration_002_create_admin_user()
        
        print("All migrations completed successfully")

def migration_001_update_password_hash_length():
    """Migration 001: Update password_hash column to support longer hashes"""
    from app import db
    
    try:
        # Check if admin_users table exists using SQLAlchemy inspector
        inspector = db.inspect(db.engine)
        if 'admin_users' in inspector.get_table_names():
            print("Found existing admin_users table, updating password_hash column...")
            # Check if we're using PostgreSQL or SQLite
            if db.engine.dialect.name == 'postgresql':
                with db.engine.connect() as connection:
                    connection.execute(text("ALTER TABLE admin_users ALTER COLUMN password_hash TYPE VARCHAR(255);"))
                    connection.commit()
                    print("✅ Updated password_hash column length to 255 characters (PostgreSQL)")
            elif db.engine.dialect.name == 'sqlite':
                # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
                print("SQLite detected - will recreate table with correct schema")
                with db.engine.connect() as connection:
                    connection.execute(text("DROP TABLE IF EXISTS admin_users;"))
                    connection.commit()
                    print("Dropped existing admin_users table (SQLite)")
            else:
                print(f"Unknown database dialect: {db.engine.dialect.name}")
        else:
            print("admin_users table doesn't exist yet, will be created with correct schema")
    except Exception as e:
        print(f"Password hash column update failed: {e}")
        # If update fails, drop and recreate the table
        try:
            print("Attempting to recreate admin_users table...")
            with db.engine.connect() as connection:
                if db.engine.dialect.name == 'postgresql':
                    connection.execute(text("DROP TABLE IF EXISTS admin_users CASCADE;"))
                else:
                    connection.execute(text("DROP TABLE IF EXISTS admin_users;"))
                connection.commit()
                print("Dropped existing admin_users table")
        except Exception as drop_error:
            print(f"Could not drop table: {drop_error}")

def migration_002_create_admin_user():
    """Migration 002: Create admin user from environment variables"""
    from app import AdminUser, db
    
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    
    if not admin_username or not admin_password:
        raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD environment variables must be set for production deployment")
    
    # Check if admin user already exists
    existing_admin = AdminUser.query.filter_by(username=admin_username).first()
    
    if not existing_admin:
        admin_user = AdminUser(username=admin_username)
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
        db.session.commit()
        print(f"Created admin user: {admin_username}")
    else:
        # Update password if it's different
        if not existing_admin.check_password(admin_password):
            existing_admin.set_password(admin_password)
            db.session.commit()
            print(f"Updated password for admin user: {admin_username}")
        else:
            print(f"Admin user {admin_username} already exists with correct password")

def migration_003_add_currency_fields():
    """Migration 003: Add admin_notes and rate range fields to currency table"""
    from app import db
    
    try:
        # Check if currency table exists and if new columns need to be added
        inspector = db.inspect(db.engine)
        if 'currency' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('currency')]
            
            # Check which columns need to be added
            columns_to_add = []
            
            if 'admin_notes' not in columns:
                columns_to_add.append('admin_notes')
            if 'min_buying_rate_to_aed' not in columns:
                columns_to_add.append('min_buying_rate_to_aed')
            if 'max_buying_rate_to_aed' not in columns:
                columns_to_add.append('max_buying_rate_to_aed')
            if 'min_selling_rate_to_aed' not in columns:
                columns_to_add.append('min_selling_rate_to_aed')
            if 'max_selling_rate_to_aed' not in columns:
                columns_to_add.append('max_selling_rate_to_aed')
            if 'notes_updated_at' not in columns:
                columns_to_add.append('notes_updated_at')
            
            if columns_to_add:
                print(f"Adding columns to currency table: {columns_to_add}")
                
                if db.engine.dialect.name == 'postgresql':
                    with db.engine.connect() as connection:
                        if 'admin_notes' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN admin_notes TEXT;"))
                        if 'min_buying_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN min_buying_rate_to_aed FLOAT;"))
                        if 'max_buying_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN max_buying_rate_to_aed FLOAT;"))
                        if 'min_selling_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN min_selling_rate_to_aed FLOAT;"))
                        if 'max_selling_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN max_selling_rate_to_aed FLOAT;"))
                        if 'notes_updated_at' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN notes_updated_at TIMESTAMP;"))
                        
                        connection.commit()
                        print("✅ Updated currency table columns (PostgreSQL)")
                        
                elif db.engine.dialect.name == 'sqlite':
                    with db.engine.connect() as connection:
                        if 'admin_notes' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN admin_notes TEXT;"))
                        if 'min_buying_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN min_buying_rate_to_aed REAL;"))
                        if 'max_buying_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN max_buying_rate_to_aed REAL;"))
                        if 'min_selling_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN min_selling_rate_to_aed REAL;"))
                        if 'max_selling_rate_to_aed' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN max_selling_rate_to_aed REAL;"))
                        if 'notes_updated_at' in columns_to_add:
                            connection.execute(text("ALTER TABLE currency ADD COLUMN notes_updated_at DATETIME;"))
                        
                        connection.commit()
                        print("✅ Updated currency table columns (SQLite)")
                else:
                    print(f"Unknown database dialect: {db.engine.dialect.name}")
            else:
                print("Currency table already has all required columns")
        else:
            print("Currency table doesn't exist yet, will be created with correct schema")
            
    except Exception as e:
        print(f"Currency table migration failed: {e}")
        print("New columns will be created when table is created")

def migration_004_remove_old_rate_column():
    """Migration 004: Remove old rate_to_aed column that conflicts with new schema"""
    from app import db
    
    try:
        # Check if currency table exists and if old column needs to be removed
        inspector = db.inspect(db.engine)
        if 'currency' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('currency')]
            
            if 'rate_to_aed' in columns:
                print("Found old rate_to_aed column, removing it...")
                
                if db.engine.dialect.name == 'postgresql':
                    with db.engine.connect() as connection:
                        connection.execute(text("ALTER TABLE currency DROP COLUMN IF EXISTS rate_to_aed;"))
                        connection.commit()
                        print("✅ Removed old rate_to_aed column (PostgreSQL)")
                        
                elif db.engine.dialect.name == 'sqlite':
                    # SQLite doesn't support DROP COLUMN easily, so we need to recreate the table
                    print("SQLite detected - recreating table without old column...")
                    with db.engine.connect() as connection:
                        # Create new table with correct schema
                        connection.execute(text("""
                            CREATE TABLE currency_new (
                                id INTEGER PRIMARY KEY,
                                name VARCHAR(100) NOT NULL,
                                symbol VARCHAR(10) NOT NULL UNIQUE,
                                min_buying_rate_to_aed REAL,
                                max_buying_rate_to_aed REAL,
                                min_selling_rate_to_aed REAL,
                                max_selling_rate_to_aed REAL,
                                admin_notes TEXT
                            );
                        """))
                        
                        # Copy data from old table to new table
                        connection.execute(text("""
                            INSERT INTO currency_new (id, name, symbol, min_buying_rate_to_aed, max_buying_rate_to_aed, min_selling_rate_to_aed, max_selling_rate_to_aed, admin_notes)
                            SELECT id, name, symbol, min_buying_rate_to_aed, max_buying_rate_to_aed, min_selling_rate_to_aed, max_selling_rate_to_aed, admin_notes
                            FROM currency;
                        """))
                        
                        # Drop old table and rename new table
                        connection.execute(text("DROP TABLE currency;"))
                        connection.execute(text("ALTER TABLE currency_new RENAME TO currency;"))
                        
                        connection.commit()
                        print("✅ Recreated currency table without old rate_to_aed column (SQLite)")
                else:
                    print(f"Unknown database dialect: {db.engine.dialect.name}")
            else:
                print("Old rate_to_aed column not found, no action needed")
        else:
            print("Currency table doesn't exist yet")
            
    except Exception as e:
        print(f"Migration 004 failed: {e}")
        print("This may be expected if the old column doesn't exist")

def migration_005_add_note_images_table():
    """Migration 005: Add note_images table for image attachments"""
    from app import db
    
    try:
        # Check if note_images table already exists
        inspector = db.inspect(db.engine)
        if 'note_images' not in inspector.get_table_names():
            print("Creating note_images table...")
            
            if db.engine.dialect.name == 'postgresql':
                with db.engine.connect() as connection:
                    # Create the table with all required columns including caption
                    connection.execute(text("""
                        CREATE TABLE note_images (
                            id SERIAL PRIMARY KEY,
                            currency_id INTEGER NOT NULL REFERENCES currency(id) ON DELETE CASCADE,
                            filename VARCHAR(255) NOT NULL,
                            original_filename VARCHAR(255) NOT NULL,
                            file_size INTEGER NOT NULL,
                            mime_type VARCHAR(100) NOT NULL,
                            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            caption TEXT
                        );
                    """))
                    
                    # Create index for better performance
                    connection.execute(text("""
                        CREATE INDEX idx_note_images_currency_id ON note_images(currency_id);
                    """))
                    
                    connection.commit()
                    print("✅ Created note_images table with caption column and index (PostgreSQL)")
                    
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as connection:
                    # Create the table with all required columns including caption
                    connection.execute(text("""
                        CREATE TABLE note_images (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            currency_id INTEGER NOT NULL,
                            filename VARCHAR(255) NOT NULL,
                            original_filename VARCHAR(255) NOT NULL,
                            file_size INTEGER NOT NULL,
                            mime_type VARCHAR(100) NOT NULL,
                            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            caption TEXT,
                            FOREIGN KEY (currency_id) REFERENCES currency(id) ON DELETE CASCADE
                        );
                    """))
                    
                    # Create index for better performance
                    connection.execute(text("""
                        CREATE INDEX idx_note_images_currency_id ON note_images(currency_id);
                    """))
                    
                    connection.commit()
                    print("✅ Created note_images table with caption column and index (SQLite)")
            else:
                print(f"Unknown database dialect: {db.engine.dialect.name}")
                # Fallback: let SQLAlchemy create the table
                print("Using SQLAlchemy to create note_images table...")
                db.create_all()
                print("✅ Created note_images table using SQLAlchemy")
        else:
            print("note_images table already exists")
            # Verify the table has all required columns
            columns = [col['name'] for col in inspector.get_columns('note_images')]
            required_columns = ['id', 'currency_id', 'filename', 'original_filename', 'file_size', 'mime_type', 'uploaded_at', 'caption']
            missing_columns = [col for col in required_columns if col not in columns]
            if missing_columns:
                print(f"note_images table exists but missing columns: {missing_columns}")
                # This will be handled by migration_006
            else:
                print("note_images table has all required columns")
            
    except Exception as e:
        print(f"Migration 005 failed: {e}")
        print("Attempting to create note_images table using SQLAlchemy...")
        try:
            # Fallback: use SQLAlchemy to create the table
            db.create_all()
            print("✅ Created note_images table using SQLAlchemy fallback")
        except Exception as fallback_error:
            print(f"SQLAlchemy fallback also failed: {fallback_error}")
            print("Manual intervention may be required")

def migration_006_add_caption_to_note_images():
    """Migration 006: Add caption column to note_images table"""
    from app import db
    
    try:
        # Check if note_images table exists
        inspector = db.inspect(db.engine)
        if 'note_images' not in inspector.get_table_names():
            print("note_images table doesn't exist yet, skipping migration 006")
            return
        
        # Get current table schema
        columns = [col['name'] for col in inspector.get_columns('note_images')]
        
        if 'caption' not in columns:
            print("Adding caption column to note_images table...")
            
            if db.engine.dialect.name == 'postgresql':
                with db.engine.connect() as connection:
                    connection.execute(text("ALTER TABLE note_images ADD COLUMN caption TEXT;"))
                    connection.commit()
                    print("✅ Added caption column to note_images table (PostgreSQL)")
                    
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as connection:
                    connection.execute(text("ALTER TABLE note_images ADD COLUMN caption TEXT;"))
                    connection.commit()
                    print("✅ Added caption column to note_images table (SQLite)")
            else:
                print(f"Unknown database dialect: {db.engine.dialect.name}")
        else:
            print("caption column already exists in note_images table")
            
    except Exception as e:
        print(f"Migration 006 failed: {e}")
        print("caption column will be created by SQLAlchemy if needed")

def load_sample_data(Currency=None, db=None):
    """Load sample currency data for development with admin notes"""
    if Currency is None or db is None:
        from app import Currency, db
    
    # Only load sample data in development environment
    if os.environ.get('DEBUG', 'false').lower() != 'true':
        print("Skipping sample data load - not in development mode")
        return
    
    if Currency.query.count() == 0:
        from datetime import datetime, timedelta
        
        # Create timestamps for different currencies (simulating different add times)
        now = datetime.utcnow()
        
        sample_currencies = [
            # Currency with admin notes (will show notification indicator)
            Currency(name='US Dollar', symbol='USD',
                    min_buying_rate_to_aed=3.65, max_buying_rate_to_aed=3.67,
                    min_selling_rate_to_aed=3.68, max_selling_rate_to_aed=3.70,
                    admin_notes='⚠️ High volatility expected this week due to Federal Reserve meeting. Monitor rates closely for optimal exchange timing.',
                    notes_updated_at=now - timedelta(minutes=30)),
            
            # Currency without admin notes (no notification indicator)
            Currency(name='Euro', symbol='EUR',
                    min_buying_rate_to_aed=3.95, max_buying_rate_to_aed=3.97,
                    min_selling_rate_to_aed=4.00, max_selling_rate_to_aed=4.02),
            
            # Currency with admin notes (will show notification indicator)
            Currency(name='British Pound', symbol='GBP',
                    min_buying_rate_to_aed=4.50, max_buying_rate_to_aed=4.52,
                    min_selling_rate_to_aed=4.55, max_selling_rate_to_aed=4.57,
                    admin_notes='📈 Brexit-related fluctuations possible. Current rates are favorable for buying GBP.',
                    notes_updated_at=now - timedelta(hours=2)),
            
            # Currency without admin notes (no notification indicator)
            Currency(name='Japanese Yen', symbol='JPY',
                    min_buying_rate_to_aed=0.025, max_buying_rate_to_aed=0.027,
                    min_selling_rate_to_aed=0.028, max_selling_rate_to_aed=0.030),
            
            # Currency with admin notes (will show notification indicator)
            Currency(name='Canadian Dollar', symbol='CAD',
                    min_buying_rate_to_aed=2.70, max_buying_rate_to_aed=2.72,
                    min_selling_rate_to_aed=2.75, max_selling_rate_to_aed=2.77,
                    admin_notes='🛢️ Oil price changes affecting CAD rates. Best rates available for bulk exchanges over 10,000 AED.',
                    notes_updated_at=now - timedelta(days=1)),
            
            # Currency without admin notes (no notification indicator)
            Currency(name='Swiss Franc', symbol='CHF',
                    min_buying_rate_to_aed=4.10, max_buying_rate_to_aed=4.12,
                    min_selling_rate_to_aed=4.15, max_selling_rate_to_aed=4.17),
            
            # Currency with admin notes (will show notification indicator)
            Currency(name='Australian Dollar', symbol='AUD',
                    min_buying_rate_to_aed=2.45, max_buying_rate_to_aed=2.47,
                    min_selling_rate_to_aed=2.50, max_selling_rate_to_aed=2.52,
                    admin_notes='🏦 Special promotion: 0.02 AED better rate for exchanges above 5,000 AED until end of month.',
                    notes_updated_at=now - timedelta(days=3)),
            
            # Currency without admin notes (no notification indicator)
            Currency(name='Singapore Dollar', symbol='SGD',
                    min_buying_rate_to_aed=2.68, max_buying_rate_to_aed=2.70,
                    min_selling_rate_to_aed=2.73, max_selling_rate_to_aed=2.75),
        ]
        
        for currency in sample_currencies:
            db.session.add(currency)
        db.session.commit()
        print("✅ Sample currency data loaded with admin notes for development testing")
        print("   - Currencies with notes (notification indicator): USD, GBP, CAD, AUD")
        print("   - Currencies without notes (no indicator): EUR, JPY, CHF, SGD")
    else:
        print("Sample data already exists, skipping load")

if __name__ == '__main__':
    # Load environment variables from production file
    import os
    
    # Try to load from .env.production first, then fallback to .env.aws
    if os.path.exists('.env.production'):
        try:
            from dotenv import load_dotenv
            load_dotenv('.env.production')
            print("Loaded environment from .env.production")
        except Exception as e:
            print(f"Warning: Could not load .env.production using dotenv: {e}")
            print("Attempting manual environment loading...")
            # Manual loading as fallback
            try:
                with open('.env.production', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Remove quotes if present
                            value = value.strip('"\'')
                            os.environ[key] = value
                print("Successfully loaded environment variables manually")
            except Exception as manual_error:
                print(f"Manual loading also failed: {manual_error}")
    elif os.path.exists('.env.aws'):
        from dotenv import load_dotenv
        load_dotenv('.env.aws')
        print("Loaded environment from .env.aws")
    else:
        from dotenv import load_dotenv
        load_dotenv()
        print("Loaded environment from default .env")
    
    run_migrations()
    
    # Load sample data if requested
    if os.environ.get('LOAD_SAMPLE_DATA', 'false').lower() == 'true':
        load_sample_data()