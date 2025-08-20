import sqlite3
from datetime import datetime

class TournamentDB:
    def __init__(self, db_name='tournament.db'):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Tournaments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
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

        # Players table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
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

        # Rounds table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER,
            round_number INTEGER,
            status TEXT DEFAULT 'pending',
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
        )
        ''')

        # Pairings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pairings (
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

        self.conn.commit()

    def create_tournament(self, name, rounds, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO tournaments (name, rounds, start_date, end_date, status)
        VALUES (?, ?, ?, ?, 'pending')
        ''', (name, rounds, start_date, end_date))
        self.conn.commit()
        return cursor.lastrowid

    def add_player(self, tournament_id, name, rating=0, user_id=None):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO players (tournament_id, user_id, name, rating, score)
        VALUES (?, ?, ?, ?, 0)
        ''', (tournament_id, user_id, name, rating))
        self.conn.commit()
        return cursor.lastrowid

    def create_round(self, tournament_id, round_number):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO rounds (tournament_id, round_number, status, start_time)
        VALUES (?, ?, 'in_progress', ?)
        ''', (tournament_id, round_number, datetime.now().isoformat()))
        return cursor.lastrowid

    def create_pairing(self, round_id, white_player_id, black_player_id, board_number):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO pairings (round_id, white_player_id, black_player_id, board_number)
        VALUES (?, ?, ?, ?)
        ''', (round_id, white_player_id, black_player_id, board_number))
        self.conn.commit()
        return cursor.lastrowid

    def get_tournament_players(self, tournament_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT * FROM players 
        WHERE tournament_id = ?
        ORDER BY score DESC, rating DESC
        ''', (tournament_id,))
        return cursor.fetchall()

    def get_tournament_rounds(self, tournament_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT * FROM rounds 
        WHERE tournament_id = ?
        ORDER BY round_number
        ''', (tournament_id,))
        return cursor.fetchall()

    def get_round_pairings(self, round_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT p.*, 
               wp.name as white_name, 
               bp.name as black_name
        FROM pairings p
        JOIN players wp ON p.white_player_id = wp.id
        JOIN players bp ON p.black_player_id = bp.id
        WHERE p.round_id = ?
        ORDER BY p.board_number
        ''', (round_id,))
        return cursor.fetchall()

    def record_result(self, pairing_id, result):
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE pairings 
        SET result = ?
        WHERE id = ?
        ''', (result, pairing_id))
        self.conn.commit()

    def update_player_score(self, player_id, score_change):
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE players 
        SET score = score + ?
        WHERE id = ?
        ''', (score_change, player_id))
        self.conn.commit()

    def close(self):
        self.conn.close()

# Initialize database
def init_db():
    db = TournamentDB()
    db.create_tables()
    db.close()

if __name__ == '__main__':
    init_db()
