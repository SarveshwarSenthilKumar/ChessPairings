"""
Migration script to add team column to players table.
"""
import sqlite3
import os
from datetime import datetime

def migrate():
    # Connect to the database
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tournament.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if team column already exists
        cursor.execute("PRAGMA table_info(players)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'team' not in columns:
            # Add team column
            print("Adding team column to players table...")
            cursor.execute("ALTER TABLE players ADD COLUMN team TEXT")
            print("Team column added successfully.")
        else:
            print("Team column already exists in players table.")
            
        # Commit changes
        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
