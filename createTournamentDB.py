import sqlite3
import os

def create_tournament_db():
    # Create or truncate the database file
    db_file = 'tournament.db'
    if os.path.exists(db_file):
        os.remove(db_file)
    
    connection = sqlite3.connect(db_file)
    crsr = connection.cursor()

    # Players table
    crsr.execute('''CREATE TABLE players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        name TEXT NOT NULL,
        rating INTEGER DEFAULT 1200,
        title TEXT,
        federation TEXT,
        fide_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Tournaments table
    crsr.execute('''CREATE TABLE tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        time_control TEXT,
        rounds INTEGER DEFAULT 5,
        status TEXT DEFAULT 'pending',  # pending, ongoing, completed
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Tournament_players table (many-to-many relationship)
    crsr.execute('''CREATE TABLE tournament_players (
        tournament_id INTEGER,
        player_id INTEGER,
        initial_rating INTEGER,
        final_rating INTEGER,
        score REAL DEFAULT 0,
        tiebreak1 REAL DEFAULT 0,  # Buchholz
        tiebreak2 REAL DEFAULT 0,  # Sonneborn-Berger
        tiebreak3 REAL DEFAULT 0,  # Direct encounter
        PRIMARY KEY (tournament_id, player_id),
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
        FOREIGN KEY (player_id) REFERENCES players(id)
    )''')

    # Rounds table
    crsr.execute('''CREATE TABLE rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER,
        round_number INTEGER NOT NULL,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        status TEXT DEFAULT 'pending',  # pending, ongoing, completed
        FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
    )''')

    # Pairings table
    crsr.execute('''CREATE TABLE pairings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER,
        white_player_id INTEGER,
        black_player_id INTEGER,
        result TEXT,  # '1-0', '0-1', '0.5-0.5', '*'
        board_number INTEGER,
        status TEXT DEFAULT 'pending',  # pending, ongoing, completed
        FOREIGN KEY (round_id) REFERENCES rounds(id),
        FOREIGN KEY (white_player_id) REFERENCES players(id),
        FOREIGN KEY (black_player_id) REFERENCES players(id)
    )''')

    # Games table (for move history and PGN storage)
    crsr.execute('''CREATE TABLE games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pairing_id INTEGER,
        pgn TEXT,
        time_control TEXT,
        time_taken_white INTEGER,  # in seconds
        time_taken_black INTEGER,  # in seconds
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pairing_id) REFERENCES pairings(id)
    )''')

    # Create indexes for better performance
    crsr.execute('CREATE INDEX idx_tournament_players_tournament ON tournament_players(tournament_id)')
    crsr.execute('CREATE INDEX idx_tournament_players_player ON tournament_players(player_id)')
    crsr.execute('CREATE INDEX idx_rounds_tournament ON rounds(tournament_id)')
    crsr.execute('CREATE INDEX idx_pairings_round ON pairings(round_id)')
    crsr.execute('CREATE INDEX idx_pairings_players ON pairings(white_player_id, black_player_id)')
    
    connection.commit()
    crsr.close()
    connection.close()
    print(f"Tournament database created successfully at {os.path.abspath(db_file)}")

if __name__ == "__main__":
    create_tournament_db()
