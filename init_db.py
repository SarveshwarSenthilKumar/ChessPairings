"""
Database Initialization Script

This script initializes the tournament database with the required tables.
Run this script once when setting up the application for the first time.
"""
import os
import sys
from pathlib import Path

def initialize_database():
    try:
        # Add the parent directory to the path so we can import app
        current_dir = Path(__file__).parent.absolute()
        parent_dir = current_dir.parent
        if str(parent_dir) not in sys.path:
            sys.path.append(str(parent_dir))
        
        from app import init_db
        
        print("Initializing database...")
        init_db()
        print("✅ Database initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Chess Tournament Pairings - Database Initialization")
    print("=" * 50)
    print()
    
    if initialize_database():
        print("\nSetup complete! You can now start the application with 'python app.py'")
    else:
        print("\nFailed to initialize database. Please check the error message above.")
        sys.exit(1)
