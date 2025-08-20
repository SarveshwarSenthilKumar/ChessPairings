"""
Tournament Database Initialization Script

This script initializes the tournament database with all required tables.
Run this script once when setting up the application for the first time.
"""
import sqlite3
import os

def create_tournament_tables():
    try:
        # Create the instance directory if it doesn't exist
        os.makedirs('instance', exist_ok=True)
        
        # Connect to the database (creates it if it doesn't exist)
        conn = sqlite3.connect('instance/tournament.db')
        cursor = conn.cursor()
        
        # Drop existing tables if they exist (for clean setup)
        cursor.executescript('''
            DROP TABLE IF EXISTS pairings;
            DROP TABLE IF EXISTS rounds;
            DROP TABLE IF EXISTS players;
            DROP TABLE IF EXISTS tournaments;
        ''')
        
        # Create tournaments table
        cursor.execute('''
        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            rounds INTEGER DEFAULT 0,
            current_round INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create players table
        cursor.execute('''
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tournament_id INTEGER,
            name TEXT NOT NULL,
            rating INTEGER DEFAULT 0,
            score REAL DEFAULT 0.0,
            tiebreak1 REAL DEFAULT 0.0,
            tiebreak2 REAL DEFAULT 0.0,
            FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
        )
        ''')
        
        # Create rounds table
        cursor.execute('''
        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER,
            round_number INTEGER,
            status TEXT DEFAULT 'pending',
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
        )
        ''')
        
        # Create pairings table
        cursor.execute('''
        CREATE TABLE pairings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER,
            white_player_id INTEGER,
            black_player_id INTEGER,
            result TEXT DEFAULT '*',
            board_number INTEGER,
            FOREIGN KEY (round_id) REFERENCES rounds (id),
            FOREIGN KEY (white_player_id) REFERENCES players (id),
            FOREIGN KEY (black_player_id) REFERENCES players (id)
        )
        ''')
        
        # Create indexes for better performance
        cursor.executescript('''
            CREATE INDEX IF NOT EXISTS idx_players_tournament ON players(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_rounds_tournament ON rounds(tournament_id);
            CREATE INDEX IF NOT EXISTS idx_pairings_round ON pairings(round_id);
        ''')
        
        conn.commit()
        return True, "✅ Database initialized successfully!"
        
    except Exception as e:
        return False, f"❌ Error initializing database: {str(e)}"
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Chess Tournament Pairings - Database Initialization")
    print("=" * 50)
    print()
    
    success, message = create_tournament_tables()
    print(message)
    
    if success:
        print("\nSetup complete! You can now start the application with 'python app.py'")
    else:
        print("\nFailed to initialize database. Please check the error message above.")
        exit(1)
