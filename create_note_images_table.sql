-- SQL Migration Script: Create note_images table
-- Run this script directly on your production database to fix the missing table error

-- For PostgreSQL (most likely for production on EC2):
-- =====================================================

-- Check if table exists first (PostgreSQL)
-- You can run this query to check: SELECT tablename FROM pg_tables WHERE tablename = 'note_images';

-- Create the note_images table
CREATE TABLE IF NOT EXISTS note_images (
    id SERIAL PRIMARY KEY,
    currency_id INTEGER NOT NULL REFERENCES currency(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    caption TEXT
);

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_note_images_currency_id ON note_images(currency_id);

-- Verify the table was created
-- You can run this to verify: SELECT column_name FROM information_schema.columns WHERE table_name = 'note_images';

-- =====================================================
-- Alternative for SQLite (if using SQLite in production):
-- =====================================================

-- For SQLite, use this instead:
/*
CREATE TABLE IF NOT EXISTS note_images (
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

CREATE INDEX IF NOT EXISTS idx_note_images_currency_id ON note_images(currency_id);
*/

-- =====================================================
-- Verification Queries
-- =====================================================

-- To verify the table exists and has correct structure:
-- PostgreSQL:
-- SELECT tablename FROM pg_tables WHERE tablename = 'note_images';
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'note_images' ORDER BY ordinal_position;

-- SQLite:
-- SELECT name FROM sqlite_master WHERE type='table' AND name='note_images';
-- PRAGMA table_info(note_images);