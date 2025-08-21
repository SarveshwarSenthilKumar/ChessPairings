"""
Users Database Initialization Script

This script initializes the users database with the required tables.
Run this script once when setting up the application for the first time.
"""
import os
import sqlite3
from pathlib import Path

def create_users_database():
    try:
        # Create the instance directory if it doesn't exist
        os.makedirs('instance', exist_ok=True)
        
        # Connect to the database (creates it if it doesn't exist)
        conn = sqlite3.connect('instance/users.db')
        cursor = conn.cursor()
        
        # Define the users table schema
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        
        conn.commit()
        print("✅ Users database initialized successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing users database: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Chess Tournament Pairings - Users Database Initialization")
    print("=" * 50)
    print()
    
    if create_users_database():
        print("\nSetup complete! You can now start the application with 'python app.py'")
    else:
        print("\nFailed to initialize users database. Please check the error message above.")
        exit(1)
