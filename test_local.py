#!/usr/bin/env python3
"""
Local testing script for Currency Exchange application
Tests the application with proper environment variables set
"""
import os
import sys
import subprocess
import secrets

def generate_secure_credentials():
    """Generate secure credentials for testing"""
    secret_key = secrets.token_hex(32)
    admin_password = secrets.token_urlsafe(16)
    return secret_key, admin_password

def setup_test_environment():
    """Set up environment variables for local testing"""
    secret_key, admin_password = generate_secure_credentials()
    
    # Set required environment variables
    os.environ['SECRET_KEY'] = secret_key
    os.environ['ADMIN_USERNAME'] = 'admin'
    os.environ['ADMIN_PASSWORD'] = admin_password
    os.environ['DATABASE_URL'] = 'sqlite:///test_currency_exchange.db'
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEBUG'] = 'true'
    os.environ['PORT'] = '5001'
    os.environ['LOAD_SAMPLE_DATA'] = 'true'
    
    print("✅ Test environment configured:")
    print(f"   Admin Username: admin")
    print(f"   Admin Password: {admin_password}")
    print(f"   Secret Key: {secret_key[:16]}...")
    print(f"   Database: test_currency_exchange.db")
    print(f"   Port: 5001")
    
    return admin_password

def test_imports():
    """Test that all imports work correctly"""
    try:
        print("🔍 Testing imports...")
        import app
        import migrations
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_database_setup():
    """Test database initialization"""
    try:
        print("🔍 Testing database setup...")
        from app import app, db
        from migrations import run_migrations
        
        with app.app_context():
            run_migrations()
        
        print("✅ Database setup successful")
        return True
    except Exception as e:
        print(f"❌ Database setup error: {e}")
        return False

def test_application_start():
    """Test that the application can start"""
    try:
        print("🔍 Testing application startup...")
        from app import app
        
        # Test that app can be created without errors
        with app.app_context():
            # Test health endpoint
            with app.test_client() as client:
                response = client.get('/health')
                if response.status_code == 200:
                    print("✅ Health endpoint working")
                    return True
                else:
                    print(f"❌ Health endpoint returned {response.status_code}")
                    return False
    except Exception as e:
        print(f"❌ Application startup error: {e}")
        return False

def cleanup_test_files():
    """Clean up test database file"""
    test_db = 'test_currency_exchange.db'
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"🧹 Cleaned up {test_db}")

def main():
    """Run all tests"""
    print("🚀 Starting Currency Exchange Application Tests")
    print("=" * 50)
    
    # Setup test environment
    admin_password = setup_test_environment()
    
    # Run tests
    tests = [
        ("Import Test", test_imports),
        ("Database Setup Test", test_database_setup),
        ("Application Startup Test", test_application_start),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Application is ready for deployment.")
        print(f"\n🔑 Save these credentials for admin access:")
        print(f"   Username: admin")
        print(f"   Password: {admin_password}")
        print(f"\n🌐 To start the application manually:")
        print(f"   python app.py")
        print(f"   Then visit: http://localhost:5001")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        cleanup_test_files()
        return 1
    
    # Ask if user wants to clean up
    try:
        cleanup = input("\n🧹 Clean up test database? (y/N): ").lower().strip()
        if cleanup == 'y':
            cleanup_test_files()
    except KeyboardInterrupt:
        print("\n🧹 Cleaning up...")
        cleanup_test_files()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())