import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Tuple

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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        
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
            prize_winners INTEGER DEFAULT 0
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
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                       (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count,
                       t.prize_winners as prize_winners
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
            
    def get_all_players(self) -> List[Dict[str, Any]]:
        """Get all players in the database.
        
        Returns:
            A list of dictionaries containing player data.
        """
        try:
            self.cursor.execute("""
                SELECT id, name, rating, created_at
                FROM players
                ORDER BY name
            """)
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting all players: {e}")
            return []
            
    def get_tournament_players(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all players in a specific tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A list of dictionaries containing player data with tournament-specific info.
        """
        try:
            self.cursor.execute("""
                SELECT p.id, p.name, p.rating, 
                       tp.initial_rating, tp.score, tp.tiebreak1, tp.tiebreak2, tp.tiebreak3
                FROM players p
                JOIN tournament_players tp ON p.id = tp.player_id
                WHERE tp.tournament_id = ?
                ORDER BY p.name
            """, (tournament_id,))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting players for tournament {tournament_id}: {e}")
            return []
            
    def get_tournament_players_with_scores(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all players in a tournament with their current scores.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A list of dictionaries containing player data and scores.
        """
        try:
            self.cursor.execute("""
                SELECT p.id, p.name, p.rating, tp.score, tp.initial_rating,
                       tp.tiebreak1, tp.tiebreak2, tp.tiebreak3
                FROM players p
                JOIN tournament_players tp ON p.id = tp.player_id
                WHERE tp.tournament_id = ?
                ORDER BY tp.score DESC, tp.tiebreak1 DESC, tp.tiebreak2 DESC, tp.tiebreak3 DESC, p.rating DESC
            """, (tournament_id,))
            
            players = [dict(row) for row in self.cursor.fetchall()]
            return players
            
        except sqlite3.Error as e:
            print(f"Error getting tournament players: {e}")
            return []
            
    def get_previous_pairings(self, tournament_id: int, player_id: int) -> List[int]:
        """Get a list of player IDs that the given player has already played against.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player.
            
        Returns:
            A list of player IDs that the player has already played against.
        """
        try:
            self.cursor.execute("""
                SELECT DISTINCT 
                    CASE 
                        WHEN p.white_player_id = ? THEN p.black_player_id 
                        ELSE p.white_player_id 
                    END as opponent_id
                FROM pairings p
                JOIN rounds r ON p.round_id = r.id
                WHERE r.tournament_id = ?
                AND (p.white_player_id = ? OR p.black_player_id = ?)
                AND p.status = 'completed'
            """, (player_id, tournament_id, player_id, player_id))
            
            return [row[0] for row in self.cursor.fetchall() if row[0] is not None]
            
        except sqlite3.Error as e:
            print(f"Error getting previous pairings: {e}")
            return []
            
    def generate_pairings(self, tournament_id: int, round_id: int, method: str = 'swiss') -> bool:
        """Generate pairings for a tournament round using the specified method.
        
        Args:
            tournament_id: The ID of the tournament.
            round_id: The ID of the round to generate pairings for.
            method: The pairing method to use ('swiss' or 'round_robin').
            
        Returns:
            bool: True if pairings were generated successfully, False otherwise.
        """
        try:
            # Get all players ordered by score and rating
            players = self.get_tournament_players_with_scores(tournament_id)
            
            if not players:
                return False
                
            # Get the round number for tiebreak updates
            self.cursor.execute("SELECT round_number FROM rounds WHERE id = ?", (round_id,))
            round_number = self.cursor.fetchone()[0]
            
            # For the first round, pair by rating
            if round_number == 1:
                # Sort by rating for first round
                players.sort(key=lambda x: x['rating'], reverse=True)
                
                # Calculate the number of pairings needed
                num_pairings = len(players) // 2
                pairings = []
                
                # Pair top half with bottom half manually
                for i in range(num_pairings):
                    white_player = players[i]
                    black_player = players[num_pairings + i]
                    pairings.append((white_player, black_player))
                
                # If odd number of players, give a bye to the lowest-rated player
                if len(players) % 2 != 0:
                    bye_player = players[-1]
                    pairings.append((bye_player, None))
                    
            else:
                # For subsequent rounds, use Swiss system
                # Sort by score (descending), then rating (descending)
                players.sort(key=lambda x: (-x['score'], -x['rating']))
                
                # Track which players have been paired
                paired = set()
                pairings = []
                
                # First pass: Try to pair players with the same score who haven't played before
                for i in range(len(players)):
                    player1 = players[i]
                    
                    # Skip if already paired
                    if player1['id'] in paired:
                        continue
                    
                    # Get list of players this player has already played against
                    previous_opponents = self.get_previous_pairings(tournament_id, player1['id'])
                    
                    # Try to find the highest-ranked opponent with the same score
                    for j in range(i + 1, len(players)):
                        player2 = players[j]
                        
                        # Skip if already paired, different score group, or already played
                        if (player2['id'] in paired or 
                            player2['score'] != player1['score'] or
                            player2['id'] in previous_opponents or
                            player2['id'] == player1['id']):
                            continue
                        
                        # Found a valid opponent
                        if player1['rating'] >= player2['rating']:
                            pairings.append((player1, player2))  # player1 is white
                        else:
                            pairings.append((player2, player1))  # player2 is white
                            
                        paired.add(player1['id'])
                        paired.add(player2['id'])
                        break
                
                # Get all unpaired players
                unpaired = [p for p in players if p['id'] not in paired]
                
                # If we have an odd number of players, handle the bye
                if len(unpaired) % 2 != 0:
                    # Track players who haven't had a bye yet
                    potential_bye_players = []
                    
                    # Check each unpaired player's bye history
                    for player in unpaired:
                        previous_pairings = self.get_player_pairing_history(tournament_id, player['id'])
                        bye_count = len([p for p in previous_pairings if p['black_player_id'] is None])
                        potential_bye_players.append({
                            'player': player,
                            'bye_count': bye_count,
                            'rating': player['rating']
                        })
                    
                    # Sort by: 1) fewest byes, 2) lowest rating
                    potential_bye_players.sort(key=lambda x: (x['bye_count'], x['rating']))
                    
                    # Select the best candidate for a bye
                    if potential_bye_players:
                        bye_candidate = potential_bye_players[0]['player']
                        
                        # Add the bye pairing
                        pairings.append((bye_candidate, None))
                        paired.add(bye_candidate['id'])
                        
                        # Remove from unpaired list
                        unpaired = [p for p in unpaired if p['id'] != bye_candidate['id']]
                
                # Second pass: Pair remaining unpaired players with the same score
                i = 0
                while i < len(unpaired):
                    player1 = unpaired[i]
                    
                    # Skip if already paired
                    if player1['id'] in paired:
                        i += 1
                        continue
                    
                    # Get previous opponents for this player
                    previous_opponents = self.get_previous_pairings(tournament_id, player1['id'])
                    
                    # Look for an opponent with the same score who hasn't been paired yet
                    opponent_found = False
                    for j in range(i + 1, len(unpaired)):
                        player2 = unpaired[j]
                        
                        # Skip if already paired or different score
                        if player2['id'] in paired or player2['score'] != player1['score']:
                            continue
                            
                        # Skip if they've played before
                        if player2['id'] in previous_opponents or player2['id'] == player1['id']:
                            continue
                        
                        # Found a valid opponent
                        if player1['rating'] >= player2['rating']:
                            pairings.append((player1, player2))  # player1 is white
                        else:
                            pairings.append((player2, player1))  # player2 is white
                            
                        paired.add(player1['id'])
                        paired.add(player2['id'])
                        opponent_found = True
                        break
                    
                    if not opponent_found:
                        i += 1
                
                # Third pass: Pair remaining unpaired players with closest score
                remaining = [p for p in unpaired if p['id'] not in paired]
                remaining.sort(key=lambda x: (-x['score'], -x['rating']))
                
                # Pair remaining players
                i = 0
                while i < len(remaining):
                    player1 = remaining[i]
                    
                    # Skip if already paired
                    if player1['id'] in paired:
                        i += 1
                        continue
                    
                    # Find the next available opponent with the closest score
                    best_opponent = None
                    best_score_diff = float('inf')
                    
                    for j in range(i + 1, len(remaining)):
                        player2 = remaining[j]
                        
                        # Skip if already paired
                        if player2['id'] in paired:
                            continue
                            
                        # Calculate score difference
                        score_diff = abs(player1['score'] - player2['score'])
                        
                        # If this is a better match (closer score) than previous best
                        if score_diff < best_score_diff:
                            best_opponent = player2
                            best_score_diff = score_diff
                    
                    # If we found an opponent, pair them
                    if best_opponent:
                        if player1['rating'] >= best_opponent['rating']:
                            pairings.append((player1, best_opponent))
                        else:
                            pairings.append((best_opponent, player1))
                            
                        paired.add(player1['id'])
                        paired.add(best_opponent['id'])
                    
                    # Move to next unpaired player
                    i += 1
                
                # This check is no longer needed as we handle byes earlier
                # and should never have an unpaired player at this point
            
            # Save pairings to database
            for i, (white, black) in enumerate(pairings, 1):
                # Use the create_pairing method which handles both regular and bye pairings
                black_id = black['id'] if black else None
                self.create_pairing(round_id, white['id'], black_id, i)
            
            # Update round status
            self.cursor.execute("""
                UPDATE rounds 
                SET status = 'in_progress', 
                    start_time = datetime('now')
                WHERE id = ?
            """, (round_id,))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error generating pairings: {e}")
            self.conn.rollback()
            return False
            
    def add_player_to_tournament(self, tournament_id: int, player_id: int) -> bool:
        """Add a player to a tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player to add.
            
        Returns:
            bool: True if the player was added, False if they were already in the tournament.
        """
        try:
            # Get player's current rating
            self.cursor.execute("SELECT rating FROM players WHERE id = ?", (player_id,))
            result = self.cursor.fetchone()
            if not result:
                return False
                
            rating = result[0]
            
            # Try to insert the player
            self.cursor.execute("""
                INSERT INTO tournament_players (tournament_id, player_id, initial_rating)
                VALUES (?, ?, ?)
            """, (tournament_id, player_id, rating))
            
            self.conn.commit()
            return True
            
        except sqlite3.IntegrityError:
            # Player is already in the tournament
            return False
            
        except sqlite3.Error as e:
            print(f"Error adding player {player_id} to tournament {tournament_id}: {e}")
            self.conn.rollback()
            return False
            
    def remove_player_from_tournament(self, tournament_id: int, player_id: int) -> bool:
        """Remove a player from a tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player to remove.
            
        Returns:
            bool: True if the player was removed, False otherwise.
        """
        try:
            self.cursor.execute("""
                DELETE FROM tournament_players 
                WHERE tournament_id = ? AND player_id = ?
            """, (tournament_id, player_id))
            
            if self.cursor.rowcount == 0:
                return False  # Player wasn't in the tournament
                
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error removing player {player_id} from tournament {tournament_id}: {e}")
            self.conn.rollback()
            return False
            
    def get_all_tournaments(self):
        """Get all tournaments from the database."""
        try:
            self.cursor.execute("""
                SELECT id, name, location, start_date, end_date, 
                       rounds, time_control, status, created_at, creator_id
                FROM tournaments
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting tournaments: {e}")
            return []
            
    def get_tournaments_by_creator(self, creator_id: int) -> List[Dict[str, Any]]:
        """Get all tournaments created by a specific user."""
        try:
            self.cursor.execute("""
                SELECT t.*, 
                       (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count
                FROM tournaments t
                WHERE t.creator_id = ?
                ORDER BY t.start_date DESC, t.created_at DESC
            """, (creator_id,))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting tournaments by creator {creator_id}: {e}")
            return []
            
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
            rounds, status, location, created_at, creator_id, description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            kwargs.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            kwargs.get('creator_id'),
            kwargs.get('description', '')
        )
        
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error creating tournament: {e}")
            self.conn.rollback()
            return None

# ... (rest of the code remains the same)
    # Pairing operations
    def create_pairing(self, round_id: int, white_id: int, black_id: Optional[int], board_number: int) -> int:
        """Create a new pairing for a round.
        
        Args:
            round_id: ID of the round
            white_id: ID of the white player
            black_id: ID of the black player, or None for a bye
            board_number: Board number for the pairing
            
        Returns:
            ID of the created pairing
        """
        if black_id is None:
            # This is a bye - automatically set result to 1-0 and status to completed
            query = """
            INSERT INTO pairings (round_id, white_player_id, black_player_id, board_number, status, result)
            VALUES (?, ?, NULL, ?, 'completed', '1-0')
            """
            self.cursor.execute(query, (round_id, white_id, board_number))
            
            # Update the player's score for the bye
            self.cursor.execute("""
                UPDATE tournament_players 
                SET score = score + 1 
                WHERE player_id = ? 
                AND tournament_id = (SELECT tournament_id FROM rounds WHERE id = ?)
            """, (white_id, round_id))
        else:
            # Regular pairing
            query = """
            INSERT INTO pairings (round_id, white_player_id, black_player_id, board_number, status)
            VALUES (?, ?, ?, ?, 'pending')
            """
            self.cursor.execute(query, (round_id, white_id, black_id, board_number))
        
        self.conn.commit()
        return self.cursor.lastrowid

    def record_result(self, pairing_id: int, result: Optional[str]) -> bool:
        """
        Record the result of a game.
        
        Args:
            pairing_id: The ID of the pairing
            result: The game result ('1-0', '0-1', '0.5-0.5', or None to clear the result)
            
        Returns:
            bool: True if the result was recorded successfully, False otherwise
        """
        try:
            # Get the current result to handle score adjustments correctly
            current_result = self.cursor.execute(
                "SELECT result, white_player_id, black_player_id, round_id FROM pairings WHERE id = ?",
                (pairing_id,)
            ).fetchone()
            
            if not current_result:
                return False
                
            current_result = dict(current_result)
            
            # Start a transaction
            self.cursor.execute("BEGIN TRANSACTION")
            
            # Clear previous result's impact on scores if it exists
            if current_result['result']:
                if current_result['result'] == '1-0':
                    # Remove white's win
                    self.cursor.execute("""
                        UPDATE tournament_players 
                        SET score = score - 1 
                        WHERE player_id = ?
                    """, (current_result['white_player_id'],))
                elif current_result['result'] == '0-1':
                    # Remove black's win
                    self.cursor.execute("""
                        UPDATE tournament_players 
                        SET score = score - 1 
                        WHERE player_id = ?
                    """, (current_result['black_player_id'],))
                elif current_result['result'] == '0.5-0.5':
                    # Remove draw points
                    self.cursor.execute("""
                        UPDATE tournament_players 
                        SET score = score - 0.5 
                        WHERE player_id IN (?, ?)
                    """, (current_result['white_player_id'], current_result['black_player_id']))
            
            # Update the pairing with the new result
            if result is None:
                # Clear the result
                self.cursor.execute(
                    "UPDATE pairings SET result = NULL, status = 'scheduled' WHERE id = ?",
                    (pairing_id,)
                )
            else:
                # Set the new result
                self.cursor.execute(
                    "UPDATE pairings SET result = ?, status = 'completed' WHERE id = ?",
                    (result, pairing_id)
                )
                
                # Update player scores based on the new result
                if result == '1-0':
                    # White wins
                    self.cursor.execute("""
                        UPDATE tournament_players 
                        SET score = score + 1 
                        WHERE player_id = ?
                    """, (current_result['white_player_id'],))
                elif result == '0-1':
                    # Black wins
                    self.cursor.execute("""
                        UPDATE tournament_players 
                        SET score = score + 1 
                        WHERE player_id = ?
                    """, (current_result['black_player_id'],))
                elif result == '0.5-0.5':
                    # Draw
                    self.cursor.execute("""
                        UPDATE tournament_players 
                        SET score = score + 0.5 
                        WHERE player_id IN (?, ?)
                    """, (current_result['white_player_id'], current_result['black_player_id']))
            
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
        """Get current tournament standings with all required fields for the standings page."""
        # First get all players in the tournament
        query = """
        SELECT p.id, p.name, p.rating
        FROM players p
        JOIN tournament_players tp ON p.id = tp.player_id
        WHERE tp.tournament_id = ?
        """
        self.cursor.execute(query, (tournament_id,))
        players = [dict(row) for row in self.cursor.fetchall()]
        
        # Get all completed pairings for this tournament
        query = """
        SELECT 
            pr.white_player_id, 
            pr.black_player_id, 
            pr.result,
            r.round_number
        FROM pairings pr
        JOIN rounds r ON pr.round_id = r.id
        WHERE r.tournament_id = ? AND pr.result IS NOT NULL
        """
        self.cursor.execute(query, (tournament_id,))
        pairings = self.cursor.fetchall()
        
        # Initialize player stats
        for player in players:
            player['wins'] = 0
            player['losses'] = 0
            player['draws'] = 0
            player['points'] = 0.0
            player['games_played'] = 0
            player['opponents'] = []
            player['opponents_score'] = 0.0
            player['buchholz'] = 0.0
            player['performance'] = 0.0
        
        # Calculate basic stats (wins, losses, draws, points)
        player_map = {p['id']: p for p in players}
        
        for pairing in pairings:
            white_id = pairing['white_player_id']
            black_id = pairing['black_player_id']
            result = pairing['result']
            
            if white_id in player_map and black_id in player_map:
                white = player_map[white_id]
                black = player_map[black_id]
                
                # Record opponents for tiebreaks
                white['opponents'].append(black_id)
                black['opponents'].append(white_id)
                
                # Update games played
                white['games_played'] += 1
                black['games_played'] += 1
                
                # Update results
                if result == '1-0':
                    white['wins'] += 1
                    white['points'] += 1.0
                    black['losses'] += 1
                elif result == '0-1':
                    black['wins'] += 1
                    black['points'] += 1.0
                    white['losses'] += 1
                elif result == '0.5-0.5':
                    white['draws'] += 1
                    black['draws'] += 1
                    white['points'] += 0.5
                    black['points'] += 0.5
        
        # Calculate tiebreaks (Buchholz, etc.)
        for player in players:
            # Calculate performance rating (simplified)
            total_games = player['wins'] + player['losses'] + player['draws']
            if total_games > 0:
                player['performance'] = round((player['wins'] + (player['draws'] * 0.5)) / total_games * 100)
            
            # Calculate Buchholz (sum of opponents' scores)
            buchholz = 0.0
            for opp_id in player['opponents']:
                if opp_id in player_map:
                    buchholz += player_map[opp_id]['points']
            player['buchholz'] = buchholz
            
            # Add trend (same as performance for now)
            player['trend'] = player['performance']
            
            # Add tiebreak fields for sorting
            player['tiebreak1'] = player['points']  # Primary sort by points
            player['tiebreak2'] = buchholz  # Secondary sort by Buchholz
            player['tiebreak3'] = player['performance']  # Tertiary sort by performance
        
        # Sort standings
        standings = sorted(
            players, 
            key=lambda x: (-x['points'], -x['buchholz'], -x['performance'], -x['rating'])
        )
        
        return standings

    def get_pairings(self, round_id: int) -> List[Dict[str, Any]]:
        """Get all pairings for a round."""
        query = """
        SELECT 
            p.id, 
            p.board_number, 
            p.status, 
            p.result,
            p.white_player_id,
            p.black_player_id,
            w.name as white_name, 
            w.rating as white_rating,
            b.name as black_name, 
            b.rating as black_rating
        FROM pairings p
        LEFT JOIN players w ON p.white_player_id = w.id
        LEFT JOIN players b ON p.black_player_id = b.id
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

    def add_player_to_tournament(self, tournament_id: int, player_id: int) -> bool:
        """Add a player to a tournament."""
        try:
            # Get player's current rating
            self.cursor.execute("SELECT rating FROM players WHERE id = ?", (player_id,))
            result = self.cursor.fetchone()
            if not result:
                return False
                    
            rating = result[0]
            
            # Try to insert the player
            self.cursor.execute("""
                INSERT INTO tournament_players (tournament_id, player_id, initial_rating)
                VALUES (?, ?, ?)
            """, (tournament_id, player_id, rating))
            
            self.conn.commit()
            return True
            
        except sqlite3.IntegrityError:
            # Player is already in the tournament
            self.conn.rollback()
            return False
            
        except sqlite3.Error as e:
            print(f"Error adding player to tournament: {e}")
            self.conn.rollback()
            return False
