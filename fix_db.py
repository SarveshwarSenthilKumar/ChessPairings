import sqlite3
import os

def recreate_database():
    # Remove existing database file if it exists
    db_path = 'tournament.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create the tournaments table with creator_id and description
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        rounds INTEGER DEFAULT 5,
        time_control TEXT,
        status TEXT DEFAULT 'upcoming',
        created_at TEXT NOT NULL,
        creator_id INTEGER NOT NULL,
        description TEXT,
        prize_winners INTEGER DEFAULT 0
    )
    """)
    
    # Create other necessary tables...
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    print("Database recreated successfully with correct schema!")

if __name__ == "__main__":
    recreate_database()
