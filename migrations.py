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

def load_sample_data():
    """Load sample currency data for development"""
    from app import Currency
    
    if Currency.query.count() == 0:
        sample_currencies = [
            Currency(name='US Dollar', symbol='USD',
                    min_buying_rate_to_aed=3.65, max_buying_rate_to_aed=3.67,
                    min_selling_rate_to_aed=3.68, max_selling_rate_to_aed=3.70),
            Currency(name='Euro', symbol='EUR',
                    min_buying_rate_to_aed=3.95, max_buying_rate_to_aed=3.97,
                    min_selling_rate_to_aed=4.00, max_selling_rate_to_aed=4.02),
            Currency(name='British Pound', symbol='GBP',
                    min_buying_rate_to_aed=4.50, max_buying_rate_to_aed=4.52,
                    min_selling_rate_to_aed=4.55, max_selling_rate_to_aed=4.57),
            Currency(name='Japanese Yen', symbol='JPY',
                    min_buying_rate_to_aed=0.025, max_buying_rate_to_aed=0.027,
                    min_selling_rate_to_aed=0.028, max_selling_rate_to_aed=0.030),
        ]
        for currency in sample_currencies:
            db.session.add(currency)
        db.session.commit()
        print("Sample currency data loaded")

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