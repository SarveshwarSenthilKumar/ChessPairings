import sqlite3
import os

def create_databases():
    print("Starting database initialization...")
    
    # Create users database
    users_db = 'users.db'
    if os.path.exists(users_db):
        print(f"Removing existing {users_db}...")
        os.remove(users_db)
    
    print(f"Creating {users_db}...")
    conn_users = sqlite3.connect(users_db)
    cursor_users = conn_users.cursor()
    
    # Create users table
    cursor_users.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT UNIQUE,
        name TEXT,
        dateJoined TEXT,
        is_admin BOOLEAN DEFAULT 0
    )
    ''')
    
    # Add a default admin user
    cursor_users.execute("""
    INSERT INTO users (username, password, email, name, dateJoined, is_admin)
    VALUES (?, ?, ?, ?, datetime('now'), 1)
    """, ('admin', 'admin123', 'admin@example.com', 'Admin User'))
    
    conn_users.commit()
    conn_users.close()
    print(f"Successfully created {users_db}")
    
    # Create tournament database
    tournament_db = 'tournament.db'
    if os.path.exists(tournament_db):
        print(f"Removing existing {tournament_db}...")
        os.remove(tournament_db)
    
    print(f"Creating {tournament_db}...")
    conn_tournament = sqlite3.connect(tournament_db)
    cursor_tournament = conn_tournament.cursor()
    
    # Enable foreign keys
    cursor_tournament.execute("PRAGMA foreign_keys = ON;")
    
    # Create tournaments table
    cursor_tournament.execute('''
    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        start_date TEXT,
        end_date TEXT,
        location TEXT,
        time_control TEXT,
        rounds INTEGER NOT NULL DEFAULT 5,
        current_round INTEGER DEFAULT 0,
        status TEXT DEFAULT 'upcoming',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create players table
    cursor_tournament.execute('''
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
    cursor_tournament.execute('''
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
    cursor_tournament.execute('''
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
    )
    ''')
    
    # Create matches table
    cursor_tournament.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER NOT NULL,
        board_number INTEGER,
        white_player_id INTEGER,
        black_player_id INTEGER,
        result TEXT,
        FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
        FOREIGN KEY (white_player_id) REFERENCES players(id),
        FOREIGN KEY (black_player_id) REFERENCES players(id)
    )
    ''')
    
    conn_tournament.commit()
    conn_tournament.close()
    
    print(f"Successfully created {tournament_db}")
    print("\nDatabase initialization completed successfully!")
    print("You can now start the application.")

if __name__ == "__main__":
    try:
        create_databases()
    except Exception as e:
        print(f"Error initializing databases: {str(e)}")
