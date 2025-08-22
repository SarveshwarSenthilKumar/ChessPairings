import os
import sqlite3

def create_database():
    # Remove existing database if it exists
    if os.path.exists('tournament.db'):
        os.remove('tournament.db')
    
    # Connect to the database (this will create it)
    conn = sqlite3.connect('tournament.db')
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute("PRAGMA foreign_keys = ON")
    
    # Create tables
    c.execute('''
    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        rounds INTEGER DEFAULT 5,
        time_control TEXT,
        status TEXT DEFAULT 'upcoming',
        created_at TEXT NOT NULL
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        rating INTEGER DEFAULT 1200,
        title TEXT,
        federation TEXT,
        fide_id TEXT
    )
    ''')
    
    # Add more tables as needed...
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == "__main__":
    create_database()
