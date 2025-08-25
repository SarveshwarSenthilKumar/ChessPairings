import os
import sqlite3
from datetime import datetime

def init_database():
    db_path = 'tournament_new.db'
    
    # Remove existing database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create tournaments table
        cursor.execute('''
        CREATE TABLE tournaments (
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
        ''')
        
        # Add some test data
        cursor.execute('''
        INSERT INTO tournaments (
            name, location, start_date, end_date, rounds, 
            time_control, status, created_at, creator_id, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Test Tournament', 'Test Location', 
            '2023-01-01', '2023-01-07', 5, 
            '90+30', 'upcoming', 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            1, 'Test tournament description'
        ))
        
        conn.commit()
        print(f"Successfully initialized database at {db_path}")
        
        # Verify the table was created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("\nTables in the database:", [row[0] for row in cursor.fetchall()])
        
        # Show the tournaments table structure
        print("\nTournaments table structure:")
        cursor.execute("PRAGMA table_info(tournaments)")
        for column in cursor.fetchall():
            print(f"- {column[1]}: {column[2]}")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    init_database()
