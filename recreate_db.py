import os
import sqlite3

def recreate_database():
    db_path = 'tournament.db'
    
    # Remove existing database file if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create the tournaments table with all required columns
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
        
        # Create other necessary tables...
        
        conn.commit()
        print("Database recreated successfully with correct schema!")
        
    except Exception as e:
        print(f"Error recreating database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    recreate_database()
