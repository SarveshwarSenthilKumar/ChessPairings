import sqlite3
import os

def update_database():
    db_path = 'tournament.db'
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if creator_id column exists
        cursor.execute("PRAGMA table_info(tournaments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'creator_id' not in columns:
            print("Adding missing columns to tournaments table...")
            # Create a new table with the correct schema
            cursor.execute('''
            CREATE TABLE tournaments_new (
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
            
            # Copy data from old table to new table
            cursor.execute('''
            INSERT INTO tournaments_new 
            (id, name, location, start_date, end_date, rounds, time_control, status, created_at, creator_id, description, prize_winners)
            SELECT 
                id, name, location, start_date, end_date, rounds, time_control, status, created_at, 
                1 as creator_id, 
                '' as description, 
                0 as prize_winners
            FROM tournaments
            ''')
            
            # Drop old table and rename new one
            cursor.execute('DROP TABLE tournaments')
            cursor.execute('ALTER TABLE tournaments_new RENAME TO tournaments')
            print("Successfully updated tournaments table schema!")
        else:
            print("Database schema is already up to date.")
            
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        conn.commit()
        conn.close()

if __name__ == "__main__":
    update_database()
