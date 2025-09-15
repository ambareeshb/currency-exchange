#!/usr/bin/env python3
"""
Standalone migration script to create note_images table in production
Run this script if the note_images table is missing in production database
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

def create_note_images_table():
    """Create note_images table if it doesn't exist"""
    
    # Load environment variables
    load_dotenv()
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    print(f"Connecting to database...")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Check if table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"Existing tables: {tables}")
        
        if 'note_images' in tables:
            print("✅ note_images table already exists")
            
            # Verify columns
            columns = [col['name'] for col in inspector.get_columns('note_images')]
            required_columns = ['id', 'currency_id', 'filename', 'original_filename', 'file_size', 'mime_type', 'uploaded_at', 'caption']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                print(f"⚠️  Missing columns: {missing_columns}")
                return False
            else:
                print("✅ All required columns present")
                return True
        
        print("Creating note_images table...")
        
        with engine.connect() as connection:
            if engine.dialect.name == 'postgresql':
                # PostgreSQL version
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
                print("✅ Created note_images table with index (PostgreSQL)")
                
            elif engine.dialect.name == 'sqlite':
                # SQLite version
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
                print("✅ Created note_images table with index (SQLite)")
                
            else:
                print(f"❌ Unsupported database dialect: {engine.dialect.name}")
                return False
        
        # Verify creation
        inspector = inspect(engine)
        if 'note_images' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('note_images')]
            print(f"✅ Table created successfully with columns: {columns}")
            return True
        else:
            print("❌ Table creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error creating note_images table: {e}")
        return False

if __name__ == '__main__':
    print("=== Note Images Table Migration ===")
    print("This script will create the note_images table if it doesn't exist")
    print()
    
    success = create_note_images_table()
    
    if success:
        print()
        print("✅ Migration completed successfully!")
        print("The note_images table is now ready for use.")
    else:
        print()
        print("❌ Migration failed!")
        print("Please check the error messages above and try again.")
        sys.exit(1)