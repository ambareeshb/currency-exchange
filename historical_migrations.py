"""
Historical tracking migrations for Currency Exchange Admin App
"""
import os
from werkzeug.security import generate_password_hash
from sqlalchemy import text

def run_historical_migrations():
    """Run all historical tracking database migrations"""
    from app import app, db
    
    with app.app_context():
        print("Running historical tracking migrations...")
        
        # Migration 007: Create currency_history table
        print("Running migration 007: Create currency_history table...")
        migration_007_create_currency_history_table()
        
        # Migration 008: Add soft delete columns to note_images
        print("Running migration 008: Add soft delete to note_images...")
        migration_008_add_soft_delete_to_note_images()
        
        # Migration 009: Create note_history table
        print("Running migration 009: Create note_history table...")
        migration_009_create_note_history_table()
        
        print("All historical tracking migrations completed successfully")

def migration_007_create_currency_history_table():
    """Migration 007: Create currency_history table for tracking all currency changes"""
    from app import db
    
    try:
        # Check if currency_history table already exists
        inspector = db.inspect(db.engine)
        if 'currency_history' not in inspector.get_table_names():
            print("Creating currency_history table...")
            
            if db.engine.dialect.name == 'postgresql':
                with db.engine.connect() as connection:
                    connection.execute(text("""
                        CREATE TABLE currency_history (
                            id SERIAL PRIMARY KEY,
                            currency_id INTEGER NOT NULL REFERENCES currency(id) ON DELETE CASCADE,
                            name VARCHAR(100) NOT NULL,
                            symbol VARCHAR(10) NOT NULL,
                            min_buying_rate_to_aed FLOAT,
                            max_buying_rate_to_aed FLOAT,
                            min_selling_rate_to_aed FLOAT,
                            max_selling_rate_to_aed FLOAT,
                            admin_notes TEXT,
                            notes_updated_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(80),
                            change_type VARCHAR(20) NOT NULL DEFAULT 'update',
                            change_reason TEXT
                        );
                    """))
                    
                    # Create indexes for better performance (one at a time for SQLite)
                    connection.execute(text("CREATE INDEX idx_currency_history_currency_id ON currency_history(currency_id);"))
                    connection.execute(text("CREATE INDEX idx_currency_history_created_at ON currency_history(created_at);"))
                    connection.execute(text("CREATE INDEX idx_currency_history_change_type ON currency_history(change_type);"))
                    
                    connection.commit()
                    print("✅ Created currency_history table with indexes (PostgreSQL)")
                    
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as connection:
                    connection.execute(text("""
                        CREATE TABLE currency_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            currency_id INTEGER NOT NULL,
                            name VARCHAR(100) NOT NULL,
                            symbol VARCHAR(10) NOT NULL,
                            min_buying_rate_to_aed REAL,
                            max_buying_rate_to_aed REAL,
                            min_selling_rate_to_aed REAL,
                            max_selling_rate_to_aed REAL,
                            admin_notes TEXT,
                            notes_updated_at DATETIME,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(80),
                            change_type VARCHAR(20) NOT NULL DEFAULT 'update',
                            change_reason TEXT,
                            FOREIGN KEY (currency_id) REFERENCES currency(id) ON DELETE CASCADE
                        );
                    """))
                    
                    # Create indexes for better performance (one at a time for SQLite)
                    connection.execute(text("CREATE INDEX idx_currency_history_currency_id ON currency_history(currency_id);"))
                    connection.execute(text("CREATE INDEX idx_currency_history_created_at ON currency_history(created_at);"))
                    connection.execute(text("CREATE INDEX idx_currency_history_change_type ON currency_history(change_type);"))
                    
                    connection.commit()
                    print("✅ Created currency_history table with indexes (SQLite)")
            else:
                print(f"Unknown database dialect: {db.engine.dialect.name}")
        else:
            print("currency_history table already exists")
            
    except Exception as e:
        print(f"Migration 007 failed: {e}")

def migration_008_add_soft_delete_to_note_images():
    """Migration 008: Add soft delete columns to note_images table"""
    from app import db
    
    try:
        # Check if note_images table exists
        inspector = db.inspect(db.engine)
        if 'note_images' not in inspector.get_table_names():
            print("note_images table doesn't exist yet, skipping migration 008")
            return
        
        # Get current table schema
        columns = [col['name'] for col in inspector.get_columns('note_images')]
        
        columns_to_add = []
        if 'deleted_at' not in columns:
            columns_to_add.append('deleted_at')
        if 'deleted_by' not in columns:
            columns_to_add.append('deleted_by')
        if 'delete_reason' not in columns:
            columns_to_add.append('delete_reason')
        
        if columns_to_add:
            print(f"Adding soft delete columns to note_images table: {columns_to_add}")
            
            if db.engine.dialect.name == 'postgresql':
                with db.engine.connect() as connection:
                    if 'deleted_at' in columns_to_add:
                        connection.execute(text("ALTER TABLE note_images ADD COLUMN deleted_at TIMESTAMP;"))
                    if 'deleted_by' in columns_to_add:
                        connection.execute(text("ALTER TABLE note_images ADD COLUMN deleted_by VARCHAR(80);"))
                    if 'delete_reason' in columns_to_add:
                        connection.execute(text("ALTER TABLE note_images ADD COLUMN delete_reason TEXT;"))
                    
                    connection.commit()
                    print("✅ Added soft delete columns to note_images table (PostgreSQL)")
                    
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as connection:
                    if 'deleted_at' in columns_to_add:
                        connection.execute(text("ALTER TABLE note_images ADD COLUMN deleted_at DATETIME;"))
                    if 'deleted_by' in columns_to_add:
                        connection.execute(text("ALTER TABLE note_images ADD COLUMN deleted_by VARCHAR(80);"))
                    if 'delete_reason' in columns_to_add:
                        connection.execute(text("ALTER TABLE note_images ADD COLUMN delete_reason TEXT;"))
                    
                    connection.commit()
                    print("✅ Added soft delete columns to note_images table (SQLite)")
            else:
                print(f"Unknown database dialect: {db.engine.dialect.name}")
        else:
            print("note_images table already has all soft delete columns")
            
    except Exception as e:
        print(f"Migration 008 failed: {e}")

def migration_009_create_note_history_table():
    """Migration 009: Create note_history table for tracking note changes"""
    from app import db
    
    try:
        # Check if note_history table already exists
        inspector = db.inspect(db.engine)
        if 'note_history' not in inspector.get_table_names():
            print("Creating note_history table...")
            
            if db.engine.dialect.name == 'postgresql':
                with db.engine.connect() as connection:
                    connection.execute(text("""
                        CREATE TABLE note_history (
                            id SERIAL PRIMARY KEY,
                            currency_id INTEGER NOT NULL REFERENCES currency(id) ON DELETE CASCADE,
                            note_type VARCHAR(20) NOT NULL,
                            content TEXT,
                            image_filename VARCHAR(255),
                            image_original_filename VARCHAR(255),
                            image_caption TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(80),
                            action_type VARCHAR(20) NOT NULL,
                            action_reason TEXT
                        );
                    """))
                    
                    # Create indexes for better performance (one at a time for SQLite)
                    connection.execute(text("CREATE INDEX idx_note_history_currency_id ON note_history(currency_id);"))
                    connection.execute(text("CREATE INDEX idx_note_history_created_at ON note_history(created_at);"))
                    connection.execute(text("CREATE INDEX idx_note_history_note_type ON note_history(note_type);"))
                    connection.execute(text("CREATE INDEX idx_note_history_action_type ON note_history(action_type);"))
                    
                    connection.commit()
                    print("✅ Created note_history table with indexes (PostgreSQL)")
                    
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as connection:
                    connection.execute(text("""
                        CREATE TABLE note_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            currency_id INTEGER NOT NULL,
                            note_type VARCHAR(20) NOT NULL,
                            content TEXT,
                            image_filename VARCHAR(255),
                            image_original_filename VARCHAR(255),
                            image_caption TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(80),
                            action_type VARCHAR(20) NOT NULL,
                            action_reason TEXT,
                            FOREIGN KEY (currency_id) REFERENCES currency(id) ON DELETE CASCADE
                        );
                    """))
                    
                    # Create indexes for better performance (one at a time for SQLite)
                    connection.execute(text("CREATE INDEX idx_note_history_currency_id ON note_history(currency_id);"))
                    connection.execute(text("CREATE INDEX idx_note_history_created_at ON note_history(created_at);"))
                    connection.execute(text("CREATE INDEX idx_note_history_note_type ON note_history(note_type);"))
                    connection.execute(text("CREATE INDEX idx_note_history_action_type ON note_history(action_type);"))
                    
                    connection.commit()
                    print("✅ Created note_history table with indexes (SQLite)")
            else:
                print(f"Unknown database dialect: {db.engine.dialect.name}")
        else:
            print("note_history table already exists")
            
    except Exception as e:
        print(f"Migration 009 failed: {e}")

if __name__ == '__main__':
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    run_historical_migrations()