"""
Database migrations for Currency Exchange Admin App
"""
import os
from werkzeug.security import generate_password_hash
from app import app, db, AdminUser

def run_migrations():
    """Run all database migrations"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Migration 001: Create admin user
        migration_001_create_admin_user()
        
        print("All migrations completed successfully")

def migration_001_create_admin_user():
    """Migration 001: Create admin user from environment variables"""
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
    run_migrations()
    
    # Load sample data if requested
    if os.environ.get('LOAD_SAMPLE_DATA', 'false').lower() == 'true':
        load_sample_data()