""
Database initialization script for Chess Tournament Manager.

This script creates both the users and tournament databases with all necessary tables.
"""
import sqlite3
import os
from datetime import datetime

def create_users_database():
    """Create and initialize the users database."""
    users_db = 'users.db'
    
    # Remove existing database if it exists
    if os.path.exists(users_db):
        os.remove(users_db)
    
    try:
        conn = sqlite3.connect(users_db)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Create users table
        cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            name TEXT,
            dateJoined TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
        ''')
        
        # Create default admin user
        cursor.execute('''
        INSERT INTO users (username, password, email, name, dateJoined, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'admin',
            'admin123',  # In production, this should be a hashed password
            'admin@example.com',
            'Administrator',
            datetime.now().isoformat(),
            1  # is_admin
        ))
        
        conn.commit()
        print("Users database created successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"Error creating users database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def create_tournament_database():
    """Create and initialize the tournament database."""
    tournament_db = 'tournament.db'
    
    # Remove existing database if it exists
    if os.path.exists(tournament_db):
        os.remove(tournament_db)
    
    try:
        conn = sqlite3.connect(tournament_db)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Read and execute schema
        with open('database_schema.sql', 'r', encoding='utf-8') as f:
            schema = f.read()
        
        # Execute each statement in the schema
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except sqlite3.Error as e:
                    print(f"Error executing statement: {statement}")
                    print(f"Error: {e}")
        
        conn.commit()
        print("Tournament database created successfully!")
        return True
        
    except Exception as e:
        print(f"Error creating tournament database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Main function to initialize both databases."""
    print("Starting database initialization...")
    
    users_success = create_users_database()
    tournament_success = create_tournament_database()
    
    if users_success and tournament_success:
        print("\n✅ Database initialization completed successfully!")
        print("   - users.db: Created with admin user (admin/admin123)")
        print("   - tournament.db: Created with all required tables")
        return True
    else:
        print("\n❌ Database initialization failed!")
        if not users_success:
            print("   - Failed to create users database")
        if not tournament_success:
            print("   - Failed to create tournament database")
        return False

if __name__ == "__main__":
    main()
        end_date TEXT,
        location TEXT,
        time_control TEXT,
        rounds INTEGER NOT NULL DEFAULT 5,
        current_round INTEGER DEFAULT 0,
        status TEXT DEFAULT 'upcoming',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(username)
    )
    ''')
    
    # Create players table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        rating INTEGER,
        federation TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create tournament_players table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tournament_players (
        tournament_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        registration_number INTEGER,
        initial_rating INTEGER,
        current_score REAL DEFAULT 0.0,
        tiebreak1 REAL DEFAULT 0.0,
        tiebreak2 REAL DEFAULT 0.0,
        tiebreak3 REAL DEFAULT 0.0,
        PRIMARY KEY (tournament_id, player_id),
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
    )
    ''')
    
    # Create rounds table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        UNIQUE(tournament_id, round_number)
    )
    ''')
    
    # Create matches table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        round_id INTEGER NOT NULL,
        board_number INTEGER NOT NULL,
        white_player_id INTEGER,
        black_player_id INTEGER,
        result TEXT,
        white_rating_change REAL,
        black_rating_change REAL,
        pgn TEXT,
        status TEXT DEFAULT 'scheduled',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
        FOREIGN KEY (white_player_id) REFERENCES players(id) ON DELETE SET NULL,
        FOREIGN KEY (black_player_id) REFERENCES players(id) ON DELETE SET NULL
    )
    ''')
    
    # Create player_byes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_byes (
        tournament_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        points_awarded REAL DEFAULT 1.0,
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (tournament_id, player_id, round_number),
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
    )
    ''')
    
    # Create user_tournament_roles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_tournament_roles (
        username TEXT NOT NULL,
        tournament_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (username, tournament_id, role),
        FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
    )
    ''')
    
    # Create indexes for better performance
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament 
    ON tournament_players(tournament_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_tournament_players_player 
    ON tournament_players(player_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_matches_tournament_round 
    ON matches(tournament_id, round_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_rounds_tournament 
    ON rounds(tournament_id)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_player_byes_tournament_player 
    ON player_byes(tournament_id, player_id)
    ''')
    
    # Create a default admin user (password: admin123 - should be changed after first login)
    default_password = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"  # bcrypt hash for 'admin123'
    cursor.execute('''
    INSERT OR IGNORE INTO users (username, password, name, emailAddress, role, accountStatus)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', ('admin', default_password, 'Administrator', 'admin@chesstournament.com', 'admin', 'active'))
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print(f"Database '{db_file}' has been created successfully!")

if __name__ == "__main__":
    create_database()
