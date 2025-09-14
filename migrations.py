"""
Database migrations for Currency Exchange Admin App
"""
import os
from werkzeug.security import generate_password_hash
from sqlalchemy import text

def run_migrations():
    """Run all database migrations"""
    from app import app, db, AdminUser
    
    print(f"Database URL: {os.environ.get('DATABASE_URL', 'Not set')}")
    print(f"Admin Username: {os.environ.get('ADMIN_USERNAME', 'Not set')}")
    print(f"Admin Password: {'Set' if os.environ.get('ADMIN_PASSWORD') else 'Not set'}")
    
    with app.app_context():
        print("Running database migrations...")
        
        # Migration 001: Update password_hash column length
        migration_001_update_password_hash_length()
        
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
    
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
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

def load_sample_data():
    """Load sample currency data for development"""
    from app import Currency
    
    if Currency.query.count() == 0:
        sample_currencies = [
            Currency(name='US Dollar', symbol='USD', rate_to_aed=0.27),
            Currency(name='Euro', symbol='EUR', rate_to_aed=0.25),
            Currency(name='British Pound', symbol='GBP', rate_to_aed=0.22),
            Currency(name='Japanese Yen', symbol='JPY', rate_to_aed=30.0),
        ]
        for currency in sample_currencies:
            db.session.add(currency)
        db.session.commit()
        print("Sample currency data loaded")

if __name__ == '__main__':
    # Load environment variables from production file
    from dotenv import load_dotenv
    import os
    
    # Try to load from .env.production first, then fallback to .env.aws
    if os.path.exists('.env.production'):
        load_dotenv('.env.production')
        print("Loaded environment from .env.production")
    elif os.path.exists('.env.aws'):
        load_dotenv('.env.aws')
        print("Loaded environment from .env.aws")
    else:
        load_dotenv()
        print("Loaded environment from default .env")
    
    run_migrations()
    
    # Load sample data if requested
    if os.environ.get('LOAD_SAMPLE_DATA', 'false').lower() == 'true':
        load_sample_data()