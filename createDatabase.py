import sqlite3
import os

def create_tables(connection):
    cursor = connection.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')
    
    # Tournaments table
    cursor.execute('''
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
        prize_winners INTEGER DEFAULT 0,
        share_token TEXT,
        win_points REAL DEFAULT 1.0,
        draw_points REAL DEFAULT 0.5,
        loss_points REAL DEFAULT 0.0,
        bye_points REAL DEFAULT 1.0,
        comments TEXT DEFAULT '',
        FOREIGN KEY (creator_id) REFERENCES users(id)
    )''')
    
    # Players table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        rating INTEGER DEFAULT 1200,
        created_at TEXT NOT NULL,
        team TEXT
    )''')
    
    # Tournament Players table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tournament_players (
        tournament_id INTEGER,
        player_id INTEGER,
        initial_rating INTEGER,
        score FLOAT DEFAULT 0.0,
        tiebreak1 FLOAT DEFAULT 0.0,
        tiebreak2 FLOAT DEFAULT 0.0,
        tiebreak3 FLOAT DEFAULT 0.0,
        requested_bye_round INTEGER,
        PRIMARY KEY (tournament_id, player_id),
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
    )''')
    
    # Rounds table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER,
        round_number INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
        UNIQUE (tournament_id, round_number)
    )''')
    
    # Pairings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pairings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER,
        white_player_id INTEGER,
        black_player_id INTEGER,
        board_number INTEGER,
        result TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
        FOREIGN KEY (white_player_id) REFERENCES players(id),
        FOREIGN KEY (black_player_id) REFERENCES players(id)
    )''')
    
    # Manual Byes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS manual_byes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER,
        FOREIGN KEY (player_id) REFERENCES players(id),
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
        UNIQUE (tournament_id, player_id, round_number)
    )''')
    
    # Admin Share Links table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_share_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        token TEXT NOT NULL,
        permissions TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        max_uses INTEGER,
        use_count INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (created_by) REFERENCES users(id),
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
        UNIQUE (token)
    )''')
    
    # Create indexes
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_tournament_players_player ON tournament_players(player_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament ON tournament_players(tournament_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_rounds_tournament ON rounds(tournament_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_pairings_round ON pairings(round_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_manual_byes_player ON manual_byes(player_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_manual_byes_tournament ON manual_byes(tournament_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_admin_share_links_token ON admin_share_links(token)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_tournaments_share_token ON tournaments(share_token)''')
    
    connection.commit()
    cursor.close()

def main():
    # Create or clear the database file
    db_path = 'users.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Connect to the database
    connection = sqlite3.connect(db_path)
    
    try:
        # Enable foreign key support
        connection.execute('PRAGMA foreign_keys = ON')
        
        # Create all tables
        create_tables(connection)
        print("Database schema created successfully!")
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    main()
