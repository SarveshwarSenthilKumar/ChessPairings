import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

class TournamentDB:
    def __init__(self, db_path: str = 'tournament.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._initialize_db()

    def _initialize_db(self):
        """Initialize the database with required tables if they don't exist."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Enable foreign key constraints
        self.cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create tables if they don't exist
        self.cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            rounds INTEGER DEFAULT 5,
            time_control TEXT,
            status TEXT DEFAULT 'upcoming',
            created_at TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rating INTEGER DEFAULT 1200,
            created_at TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS tournament_players (
            tournament_id INTEGER,
            player_id INTEGER,
            initial_rating INTEGER,
            score FLOAT DEFAULT 0.0,
            tiebreak1 FLOAT DEFAULT 0.0,
            tiebreak2 FLOAT DEFAULT 0.0,
            tiebreak3 FLOAT DEFAULT 0.0,
            PRIMARY KEY (tournament_id, player_id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER,
            round_number INTEGER NOT NULL,
            start_time TEXT,
            end_time TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, round_number)
        );
        
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
        );
        
        CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament ON tournament_players(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_tournament_players_player ON tournament_players(player_id);
        CREATE INDEX IF NOT EXISTS idx_rounds_tournament ON rounds(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_pairings_round ON pairings(round_id);
        """)
        
        self.conn.commit()
        
    def get_tournament(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """Get a single tournament by ID.
        
        Args:
            tournament_id: The ID of the tournament to retrieve.
            
        Returns:
            A dictionary containing the tournament data, or None if not found.
        """
        try:
            self.cursor.execute("""
                SELECT t.*, 
                       (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count
                FROM tournaments t
                WHERE t.id = ?
            """, (tournament_id,))
            
            result = self.cursor.fetchone()
            return dict(result) if result else None
            
        except sqlite3.Error as e:
            print(f"Error getting tournament {tournament_id}: {e}")
            return None
            
    def get_current_round(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """Get the current round for a tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A dictionary containing the current round data, or None if not found.
        """
        try:
            self.cursor.execute("""
                SELECT * FROM rounds 
                WHERE tournament_id = ? 
                ORDER BY round_number DESC 
                LIMIT 1
            """, (tournament_id,))
            
            result = self.cursor.fetchone()
            return dict(result) if result else None
            
        except sqlite3.Error as e:
            print(f"Error getting current round for tournament {tournament_id}: {e}")
            return None
            
    def get_round_pairings(self, round_id: int) -> List[Dict[str, Any]]:
        """Get all pairings for a specific round.
        
        Args:
            round_id: The ID of the round.
            
        Returns:
            A list of dictionaries containing pairing data.
        """
        try:
            self.cursor.execute("""
                SELECT p.*, 
                       w.name as white_name, w.rating as white_rating,
                       b.name as black_name, b.rating as black_rating
                FROM pairings p
                LEFT JOIN players w ON p.white_player_id = w.id
                LEFT JOIN players b ON p.black_player_id = b.id
                WHERE p.round_id = ?
                ORDER BY p.board_number
            """, (round_id,))
            
            return [dict(row) for row in self.cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Error getting pairings for round {round_id}: {e}")
            return []
            
    def get_all_tournaments(self):
        """Get all tournaments from the database."""
        try:
            self.cursor.execute("""
                SELECT id, name, location, start_date, end_date, 
                       rounds, time_control, status, created_at
                FROM tournaments
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting tournaments: {e}")
            return []
            
    def create_tournament(self, name, start_date, end_date, **kwargs):
        """Create a new tournament."""
        try:
            query = """
            INSERT INTO tournaments (
                name, start_date, end_date, location, 
                rounds, time_control, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                name,
                start_date,
                end_date,
                kwargs.get('location'),
                kwargs.get('rounds', 5),
                kwargs.get('time_control'),
                kwargs.get('status', 'upcoming'),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.lastrowid
            
        except sqlite3.Error as e:
            print(f"Error creating tournament: {e}")
            self.conn.rollback()
            return None
            
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Get a player by ID."""
        self.cursor.execute("SELECT * FROM players WHERE id = ?", (player_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    # Tournament operations
    def create_tournament(self, name: str, start_date: str, end_date: str, rounds: int = 5, **kwargs) -> int:
        """Create a new tournament.
        
        Args:
            name: Tournament name
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            rounds: Number of rounds (default: 5)
            **kwargs: Additional tournament fields (location, time_control, status, created_at)
            
        Returns:
            int: ID of the created tournament
        """
        query = """
        INSERT INTO tournaments (
            name, start_date, end_date, time_control, 
            rounds, status, location, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        # Prepare parameters
        params = (
            name,
            start_date,
            end_date,
            kwargs.get('time_control'),
            rounds,
            kwargs.get('status', 'upcoming'),
            kwargs.get('location'),
            kwargs.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error creating tournament: {e}")
            self.conn.rollback()
            return None

    def add_player_to_tournament(self, tournament_id: int, player_id: int) -> bool:
        """Add a player to a tournament."""
        try:
            # Get player's current rating
            player = self.get_player(player_id)
            if not player:
                return False
                
            query = """
            INSERT INTO tournament_players (tournament_id, player_id, initial_rating)
            VALUES (?, ?, ?)
            """
            self.cursor.execute(query, (tournament_id, player_id, player['rating']))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Player already in tournament
            return False

    # Pairing operations
    def create_pairing(self, round_id: int, white_id: int, black_id: int, board_number: int) -> int:
        """Create a new pairing for a round."""
        query = """
        INSERT INTO pairings (round_id, white_player_id, black_player_id, board_number, status)
        VALUES (?, ?, ?, ?, 'pending')
        """
        self.cursor.execute(query, (round_id, white_id, black_id, board_number))
        self.conn.commit()
        return self.cursor.lastrowid

    def record_result(self, pairing_id: int, result: str) -> bool:
        """Record the result of a game."""
        try:
            self.cursor.execute(
                "UPDATE pairings SET result = ?, status = 'completed' WHERE id = ?",
                (result, pairing_id)
            )
            
            # Update player scores in the tournament
            if result == '1-0':
                # White wins
                self.cursor.execute("""
                    UPDATE tournament_players 
                    SET score = score + 1 
                    WHERE player_id = (
                        SELECT white_player_id FROM pairings WHERE id = ?
                    )
                """, (pairing_id,))
            elif result == '0-1':
                # Black wins
                self.cursor.execute("""
                    UPDATE tournament_players 
                    SET score = score + 1 
                    WHERE player_id = (
                        SELECT black_player_id FROM pairings WHERE id = ?
                    )
                """, (pairing_id,))
            elif result == '0.5-0.5':
                # Draw
                self.cursor.execute("""
                    UPDATE tournament_players 
                    SET score = score + 0.5 
                    WHERE player_id IN (
                        SELECT white_player_id FROM pairings WHERE id = ?
                        UNION
                        SELECT black_player_id FROM pairings WHERE id = ?
                    )
                """, (pairing_id, pairing_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error recording result: {e}")
            self.conn.rollback()
            return False

    # Tournament state management
    def start_round(self, tournament_id: int, round_number: int) -> int:
        """Start a new round in the tournament."""
        query = """
        INSERT INTO rounds (tournament_id, round_number, start_time, status)
        VALUES (?, ?, datetime('now'), 'ongoing')
        """
        self.cursor.execute(query, (tournament_id, round_number))
        self.conn.commit()
        return self.cursor.lastrowid

    def complete_round(self, round_id: int) -> bool:
        """Mark a round as completed."""
        try:
            self.cursor.execute(
                "UPDATE rounds SET status = 'completed', end_time = datetime('now') WHERE id = ?",
                (round_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error completing round: {e}")
            self.conn.rollback()
            return False

    # Reporting
    def get_standings(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get current tournament standings."""
        query = """
        SELECT p.id, p.name, p.rating, tp.score, tp.tiebreak1, tp.tiebreak2, tp.tiebreak3
        FROM players p
        JOIN tournament_players tp ON p.id = tp.player_id
        WHERE tp.tournament_id = ?
        ORDER BY tp.score DESC, tp.tiebreak1 DESC, tp.tiebreak2 DESC, tp.tiebreak3 DESC, p.rating DESC
        """
        self.cursor.execute(query, (tournament_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    def get_pairings(self, round_id: int) -> List[Dict[str, Any]]:
        """Get all pairings for a round."""
        query = """
        SELECT p.id, p.board_number, p.status, p.result,
               w.name as white_name, w.rating as white_rating,
               b.name as black_name, b.rating as black_rating
        FROM pairings p
        JOIN players w ON p.white_player_id = w.id
        JOIN players b ON p.black_player_id = b.id
        WHERE p.round_id = ?
        ORDER BY p.board_number
        """
        self.cursor.execute(query, (round_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    def get_player_pairing_history(self, tournament_id: int, player_id: int) -> List[Dict[str, Any]]:
        """Get a player's pairing history in a tournament."""
        query = """
        SELECT r.round_number, 
               p1.name as opponent_name,
               CASE 
                   WHEN p.white_player_id = ? THEN 'white' 
                   ELSE 'black' 
               END as color,
               p.result,
               CASE 
                   WHEN p.result = '1-0' AND p.white_player_id = ? THEN 1
                   WHEN p.result = '0-1' AND p.black_player_id = ? THEN 1
                   WHEN p.result = '0.5-0.5' THEN 0.5
                   ELSE 0
               END as points
        FROM pairings p
        JOIN rounds r ON p.round_id = r.id
        JOIN players p1 ON 
            CASE 
                WHEN p.white_player_id = ? THEN p.black_player_id 
                ELSE p.white_player_id 
            END = p1.id
        WHERE r.tournament_id = ? 
          AND (p.white_player_id = ? OR p.black_player_id = ?)
          AND p.status = 'completed'
        ORDER BY r.round_number
        """
        params = (player_id, player_id, player_id, player_id, tournament_id, player_id, player_id)
        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]

    # Swiss pairing algorithm
    def generate_swiss_pairings(self, tournament_id: int, round_number: int) -> bool:
        """Generate Swiss pairings for the next round."""
        try:
            # Start a new round
            round_id = self.start_round(tournament_id, round_number)
            
            # Get current standings
            standings = self.get_standings(tournament_id)
            
            if not standings:
                return False
                
            # Sort players by score and rating
            players = sorted(standings, key=lambda x: (-x['score'], -x['rating']))
            
            # Track paired player IDs
            paired = set()
            board_number = 1
            
            # Simple pairing algorithm (can be enhanced with more sophisticated logic)
            for i in range(len(players)):
                if players[i]['id'] in paired:
                    continue
                    
                # Try to find an opponent with the same score
                for j in range(i + 1, len(players)):
                    if (players[j]['id'] not in paired and 
                        players[j]['score'] == players[i]['score'] and 
                        not self.have_played_before(tournament_id, players[i]['id'], players[j]['id'])):
                        
                        # Alternate colors based on round number and player index
                        if (i + round_number) % 2 == 0:
                            white, black = players[i], players[j]
                        else:
                            white, black = players[j], players[i]
                            
                        self.create_pairing(round_id, white['id'], black['id'], board_number)
                        paired.add(white['id'])
                        paired.add(black['id'])
                        board_number += 1
                        break
            
            # Handle any remaining players (bye if odd number)
            for player in players:
                if player['id'] not in paired:
                    # Assign a bye (automatic 1-0 win)
                    self.create_pairing(round_id, player['id'], None, board_number)
                    self.record_result(self.cursor.lastrowid, '1-0')
                    board_number += 1
            
            return True
            
        except Exception as e:
            print(f"Error generating pairings: {e}")
            self.conn.rollback()
            return False
    
    def have_played_before(self, tournament_id: int, player1_id: int, player2_id: int) -> bool:
        """Check if two players have played against each other in this tournament."""
        query = """
        SELECT COUNT(*) as count
        FROM pairings p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.tournament_id = ?
        AND (
            (p.white_player_id = ? AND p.black_player_id = ?) OR
            (p.white_player_id = ? AND p.black_player_id = ?)
        )
        """
        self.cursor.execute(query, (tournament_id, player1_id, player2_id, player2_id, player1_id))
        return self.cursor.fetchone()['count'] > 0
