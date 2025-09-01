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
        
        CREATE TABLE IF NOT EXISTS manual_byes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
            UNIQUE(tournament_id, player_id, round_number)
        );
        
        CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament ON tournament_players(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_tournament_players_player ON tournament_players(player_id);
        CREATE INDEX IF NOT EXISTS idx_rounds_tournament ON rounds(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_pairings_round ON pairings(round_id);
        CREATE INDEX IF NOT EXISTS idx_manual_byes_tournament ON manual_byes(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_manual_byes_player ON manual_byes(player_id);
        """)
        
        # Add requested_bye_round column if it doesn't exist
        try:
            # First, check if the column exists
            self.cursor.execute("""
                SELECT 1 FROM pragma_table_info('tournament_players') 
                WHERE name = 'requested_bye_round'
            """)
            if not self.cursor.fetchone():
                # If column doesn't exist, add it
                self.cursor.execute("""
                    ALTER TABLE tournament_players 
                    ADD COLUMN requested_bye_round INTEGER DEFAULT NULL
                """)
                self.conn.commit()
        except sqlite3.Error as e:
            print(f"Warning: Could not check/add requested_bye_round column: {e}")
            # Continue execution even if there's an error
        
        self.conn.commit()
        
    def update_tournament_status(self, tournament_id: int, status: str) -> bool:
        """Update the status of a tournament.
        
        Args:
            tournament_id: The ID of the tournament to update.
            status: The new status ('upcoming', 'in_progress', 'completed').
            
        Returns:
            True if the update was successful, False otherwise.
        """
        try:
            self.cursor.execute(
                "UPDATE tournaments SET status = ? WHERE id = ?",
                (status, tournament_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
            
        except sqlite3.Error as e:
            print(f"Error updating tournament status: {e}")
            self.conn.rollback()
            return False
            
    def update_tournament(self, tournament_id: int, **kwargs) -> bool:
        """Update tournament details.
        
        Args:
            tournament_id: The ID of the tournament to update.
            **kwargs: Tournament fields to update (name, location, start_date, end_date, 
                    rounds, time_control, description)
                    
        Returns:
            bool: True if the update was successful, False otherwise.
        """
        if not kwargs:
            return False
            
        allowed_fields = ['name', 'location', 'start_date', 'end_date', 
                        'rounds', 'time_control', 'description',
                        'win_points', 'draw_points', 'loss_points', 'bye_points']
        
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
                
        if not updates:
            return False
            
        query = f"""
            UPDATE tournaments 
            SET {', '.join(updates)}
            WHERE id = ?
        """
        
        try:
            self.cursor.execute(query, params + [tournament_id])
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False
    
    def get_tournament(self, tournament_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
        """Get a single tournament by ID with optional user access check.
        
        Args:
            tournament_id: The ID of the tournament to retrieve.
            user_id: Optional user ID to verify tournament ownership.
                   If provided, will first try to get the tournament with the user_id check,
                   and if that fails, will try without the user_id check.
            
        Returns:
            A dictionary containing the tournament data, or None if not found or access denied.
        """
        try:
            # First try with user_id check if provided
            if user_id is not None:
                query = """
                    SELECT t.*, 
                           (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count,
                           t.prize_winners as prize_winners
                    FROM tournaments t
                    WHERE t.id = ? AND t.creator_id = ?
                """
                self.cursor.execute(query, (tournament_id, user_id))
                result = self.cursor.fetchone()
                if result:
                    return dict(result)
            
            # If user_id check failed or not provided, try without user_id check
            query = """
                SELECT t.*, 
                       (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count,
                       t.prize_winners as prize_winners
                FROM tournaments t
                WHERE t.id = ?
            """
            self.cursor.execute(query, (tournament_id,))
            result = self.cursor.fetchone()
            return dict(result) if result else None
            
        except sqlite3.Error as e:
            print(f"Error getting tournament {tournament_id}: {e}")
            return None
            
    def get_tournament_by_share_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get a tournament by its share token.
        
        Args:
            token: The share token of the tournament.
            
        Returns:
            A dictionary containing the tournament data, or None if not found.
        """
        if not token:
            return None
            
        try:
            self.cursor.execute("""
                SELECT t.*, 
                       (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count
                FROM tournaments t
                WHERE t.share_token = ?
            """, (token,))
            
            result = self.cursor.fetchone()
            return dict(result) if result else None
            
        except sqlite3.Error as e:
            print(f"Error getting tournament by share token: {e}")
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
            
    def get_pairings(self, round_id: int) -> List[Dict[str, Any]]:
        """Get all pairings for a round, including byes.
        
        Args:
            round_id: The ID of the round to get pairings for.
            
        Returns:
            A list of dictionaries containing pairing information, including player details.
            Each pairing has an 'is_bye' flag set to True if it's a bye pairing.
        """
        try:
            # First, get the round details to determine the round number
            self.cursor.execute("""
                SELECT id, round_number, tournament_id 
                FROM rounds 
                WHERE id = ?
            """, (round_id,))
            round_info = self.cursor.fetchone()
            
            if not round_info:
                return []
                
            round_number = round_info['round_number']
            tournament_id = round_info['tournament_id']
            
            # Get all manual byes for this round
            self.cursor.execute("""
                SELECT mb.player_id, p.name, p.rating
                FROM manual_byes mb
                JOIN players p ON mb.player_id = p.id
                WHERE mb.tournament_id = ? AND mb.round_number = ?
            """, (tournament_id, round_number))
            
            manual_byes = {row['player_id']: dict(row) for row in self.cursor.fetchall()}
            
            # Get all pairings for the round
            self.cursor.execute("""
                SELECT 
                    p.id, p.board_number, p.status, p.result,
                    p.white_player_id, p.black_player_id,
                    w.name as white_name, w.rating as white_rating,
                    b.name as black_name, b.rating as black_rating
                FROM pairings p
                LEFT JOIN players w ON p.white_player_id = w.id
                LEFT JOIN players b ON p.black_player_id = b.id
                WHERE p.round_id = ?
                ORDER BY 
                    CASE WHEN p.black_player_id IS NULL THEN 0 ELSE 1 END,  # Bye pairings first
                    p.board_number
            """, (round_id,))
            
            pairings = []
            for row in self.cursor.fetchall():
                pairing = dict(row)
                # Add is_bye flag
                is_bye = pairing['black_player_id'] is None
                pairing['is_bye'] = is_bye
                
                # If this is a bye pairing, ensure the player is in the manual_byes set
                if is_bye and pairing['white_player_id'] in manual_byes:
                    manual_byes.pop(pairing['white_player_id'])
                    
                pairings.append(pairing)
            
            # Add any manual byes that weren't found in the pairings table
            for player_id, player_info in manual_byes.items():
                pairings.append({
                    'id': None,
                    'board_number': 0,  # Will be updated below
                    'status': 'completed',
                    'result': '1-0',  # Bye is a win for the player
                    'white_player_id': player_id,
                    'black_player_id': None,
                    'white_name': player_info['name'],
                    'white_rating': player_info['rating'],
                    'black_name': None,
                    'black_rating': None,
                    'is_bye': True
                })
            
            # Sort pairings to ensure byes are first and have sequential board numbers
            pairings.sort(key=lambda x: (0 if x['is_bye'] else 1, x.get('board_number', 0)))
            
            # Ensure board numbers are sequential
            for i, pairing in enumerate(pairings, 1):
                pairing['board_number'] = i
                
            return pairings
            
        except sqlite3.Error as e:
            print(f"Error getting pairings: {e}")
            return []
            
    def get_round_pairings(self, round_id: int) -> List[Dict[str, Any]]:
        """Get all pairings for a specific round, including byes.
        
        Args:
            round_id: The ID of the round.
            
        Returns:
            A list of pairings with player details, including byes
        """
        try:
            query = """
            SELECT 
                p.id, 
                p.white_player_id, 
                p.black_player_id, 
                p.board_number, 
                p.result, 
                p.status,
                w.name as white_name, 
                w.rating as white_rating,
                b.name as black_name, 
                b.rating as black_rating,
                CASE WHEN p.black_player_id IS NULL THEN 1 ELSE 0 END as is_bye
            FROM pairings p
            LEFT JOIN players w ON p.white_player_id = w.id
            LEFT JOIN players b ON p.black_player_id = b.id
            WHERE p.round_id = ?
            ORDER BY p.board_number
            """
            self.cursor.execute(query, (round_id,))
            pairings = [dict(row) for row in self.cursor.fetchall()]
            
            # Also get any manual byes for this round
            query = """
            SELECT 
                NULL as id,
                mb.player_id as white_player_id,
                NULL as black_player_id,
                (SELECT COALESCE(MAX(board_number), 0) FROM pairings WHERE round_id = ?) + ROW_NUMBER() OVER () as board_number,
                '1-0' as result,
                'completed' as status,
                pl.name as white_name,
                pl.rating as white_rating,
                NULL as black_name,
                NULL as black_rating,
                1 as is_bye
            FROM manual_byes mb
            JOIN players pl ON mb.player_id = pl.id
            WHERE mb.round_number = (SELECT round_number FROM rounds WHERE id = ?)
            AND mb.tournament_id = (SELECT tournament_id FROM rounds WHERE id = ?)
            AND NOT EXISTS (
                SELECT 1 FROM pairings p2 
                WHERE p2.round_id = ? 
                AND (p2.white_player_id = mb.player_id OR p2.black_player_id = mb.player_id)
            )
            """
            self.cursor.execute(query, (round_id, round_id, round_id, round_id))
            manual_byes = [dict(row) for row in self.cursor.fetchall()]
            
            # Separate regular pairings and byes
            regular_pairings = [p for p in pairings if p.get('black_player_id') is not None]
            bye_pairings = [p for p in pairings if p.get('black_player_id') is None]
            
            # Sort regular pairings by board number
            regular_pairings.sort(key=lambda x: x['board_number'])
            
            # Reassign board numbers to be sequential for regular pairings only
            for i, pairing in enumerate(regular_pairings, 1):
                pairing['board_number'] = i
                
            # Add byes at the end with board number 0 (will be displayed as 'BYE' in the UI)
            for pairing in bye_pairings:
                pairing['board_number'] = 0
                
            # Combine them back with byes at the end
            all_pairings = regular_pairings + bye_pairings
                
            return all_pairings
            
        except sqlite3.Error as e:
            print(f"Error getting round pairings: {e}")
            return []
            
    def get_all_players(self) -> List[Dict[str, Any]]:
        """Get all players in the database.
        
        Returns:
            A list of dictionaries containing player data with team information.
        """
        try:
            self.cursor.execute("""
                SELECT id, name, rating, team, created_at
                FROM players
                ORDER BY name
            """)
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting all players: {e}")
            return []
            
    def get_player_match_history(self, tournament_id: int, player_id: int) -> List[Dict[str, Any]]:
        """Get a player's match history in a tournament.
        
        Args:
            tournament_id: The ID of the tournament
            player_id: The ID of the player
            
        Returns:
            A dictionary containing match history with opponent names, results, and statistics
        """
        try:
            # Get all pairings where the player was either white or black or had a bye
            self.cursor.execute("""
                WITH player_matches AS (
                    -- Regular matches
                    SELECT 
                        r.round_number,
                        p_opponent.id as opponent_id,
                        p_opponent.name as opponent_name,
                        p_opponent.rating as opponent_rating,
                        CASE 
                            WHEN pair.white_player_id = :player_id AND pair.result IN ('1-0', '1.0-0.0') THEN '1-0'
                            WHEN pair.white_player_id = :player_id AND pair.result IN ('0-1', '0.0-1.0') THEN '0-1'
                            WHEN pair.white_player_id = :player_id AND (pair.result = '½-½' OR pair.result = '0.5-0.5' OR pair.result = '0.5-0.5 ') THEN '½-½'
                            WHEN pair.black_player_id = :player_id AND pair.result IN ('1-0', '1.0-0.0') THEN '0-1'
                            WHEN pair.black_player_id = :player_id AND pair.result IN ('0-1', '0.0-1.0') THEN '1-0'
                            WHEN pair.black_player_id = :player_id AND (pair.result = '½-½' OR pair.result = '0.5-0.5' OR pair.result = '0.5-0.5 ') THEN '½-½'
                            WHEN r.status = 'completed' AND pair.status = 'completed' AND pair.result IS NULL THEN '1-0' -- Default win if round completed without result
                            WHEN r.status = 'completed' THEN '0-1'  -- Default loss if round completed but no result
                            ELSE 'Pending'
                        END as result,
                        CASE 
                            WHEN pair.white_player_id = :player_id AND pair.result IN ('1-0', '1.0-0.0') THEN 1.0
                            WHEN pair.white_player_id = :player_id AND pair.result IN ('0-1', '0.0-1.0') THEN 0.0
                            WHEN pair.white_player_id = :player_id AND (pair.result = '½-½' OR pair.result = '0.5-0.5' OR pair.result = '0.5-0.5 ') THEN 0.5
                            WHEN pair.black_player_id = :player_id AND pair.result IN ('1-0', '1.0-0.0') THEN 0.0
                            WHEN pair.black_player_id = :player_id AND pair.result IN ('0-1', '0.0-1.0') THEN 1.0
                            WHEN pair.black_player_id = :player_id AND (pair.result = '½-½' OR pair.result = '0.5-0.5' OR pair.result = '0.5-0.5 ') THEN 0.5
                            WHEN r.status = 'completed' AND pair.status = 'completed' AND pair.result IS NULL THEN 1.0 -- Default win if round completed without result
                            WHEN r.status = 'completed' THEN 0.0  -- Default loss if round completed but no result
                            ELSE 0.0
                        END as points_earned,
                        CASE 
                            WHEN pair.white_player_id = :player_id THEN 'White'
                            WHEN pair.black_player_id = :player_id THEN 'Black'
                            ELSE 'Bye'
                        END as color,
                        pair.result as game_result,
                        r.status as round_status,
                        r.start_time as game_date,
                        FALSE as is_bye
                    FROM pairings pair
                    JOIN rounds r ON pair.round_id = r.id
                    LEFT JOIN players p_opponent ON 
                        (pair.white_player_id = p_opponent.id AND pair.black_player_id = :player_id) OR 
                        (pair.black_player_id = p_opponent.id AND pair.white_player_id = :player_id)
                    WHERE (pair.white_player_id = :player_id OR pair.black_player_id = :player_id)
                    AND r.tournament_id = :tournament_id
                    AND pair.status != 'cancelled'
                    
                    UNION ALL
                    
                    -- Manual byes
                    SELECT 
                        mb.round_number,
                        NULL as opponent_id,
                        'Bye' as opponent_name,
                        NULL as opponent_rating,
                        '1-0' as result,
                        1.0 as points_earned,
                        'Bye' as color,
                        '1-0' as game_result,
                        'completed' as round_status,
                        (SELECT start_time FROM rounds r 
                         WHERE r.tournament_id = :tournament_id 
                         AND r.round_number = mb.round_number) as game_date,
                        TRUE as is_bye
                    FROM manual_byes mb
                    WHERE mb.tournament_id = :tournament_id 
                    AND mb.player_id = :player_id
                )
                SELECT * FROM player_matches
                ORDER BY round_number
            """, {"player_id": player_id, "tournament_id": tournament_id})
            
            matches = [dict(row) for row in self.cursor.fetchall()]
            
            # First, normalize the result format
            for match in matches:
                # Convert any numeric draw format to the standard '½-½' format
                if match['result'] in ['0.5-0.5', '0.5-0.5 ']:
                    match['result'] = '½-½'
                    
                # Set default values
                match['opponent_rating'] = match.get('opponent_rating')
                match['points_earned'] = match.get('points_earned', 0.0) or 0.0
                
                # Handle byes first
                if match.get('is_bye'):
                    match['result'] = '1-0'  # Bye is always a win
                    match['points_earned'] = 1.0
                # Update status based on round status for pending matches
                elif match['round_status'] == 'completed' and match['result'] == 'Pending':
                    # If round is completed but no result, default to loss
                    match['result'] = '0-1'
                    match['points_earned'] = 0.0
            
            # Ensure all matches have the correct points_earned based on result
            for match in matches:
                if match.get('is_bye'):
                    match['result'] = '1-0'  # Bye is always a win
                    match['points_earned'] = 1.0
                elif match['result'] == '1-0':
                    match['points_earned'] = 1.0
                elif match['result'] == '0-1':
                    match['points_earned'] = 0.0
                elif match['result'] == '½-½':
                    match['points_earned'] = 0.5
                elif match['round_status'] == 'completed' and match['result'] == 'Pending':
                    # Default to loss if round is completed but no result
                    match['result'] = '0-1'
                    match['points_earned'] = 0.0
            
            # Now calculate statistics
            total_games = len(matches)
            wins = sum(1 for m in matches if m['result'] == '1-0' and not m.get('is_bye'))
            losses = sum(1 for m in matches if m['result'] == '0-1' and not m.get('is_bye'))
            draws = sum(1 for m in matches if m['result'] == '½-½')
            byes = sum(1 for m in matches if m.get('is_bye'))
            
            # Calculate total points from all matches (including byes)
            total_points = round(sum(m['points_earned'] for m in matches), 1)
            
            # Calculate performance rating if we have rated games
            rated_games = [m for m in matches if m.get('opponent_rating') and not m.get('is_bye')]
            if rated_games:
                avg_opponent_rating = sum(m['opponent_rating'] for m in rated_games) / len(rated_games)
                score_percentage = sum(m['points_earned'] for m in rated_games) / len(rated_games)
                performance_rating = int(avg_opponent_rating + 400 * (2 * score_percentage - 1))  # Standard Elo formula
            else:
                performance_rating = None
            
            # Calculate win percentage (excluding byes)
            played_games = total_games - byes
            if played_games > 0:
                win_percentage = round((wins + (draws * 0.5)) / played_games * 100, 1)
            else:
                win_percentage = 0.0
            
            return {
                'matches': matches,
                'stats': {
                    'total_games': total_games,
                    'wins': wins,
                    'losses': losses,
                    'draws': draws,
                    'byes': byes,
                    'score': total_points,  # Use the calculated total points
                    'performance_rating': round(performance_rating) if performance_rating else None,
                    'win_percentage': win_percentage
                }
            }
            
        except sqlite3.Error as e:
            print(f"Error getting match history for player {player_id} in tournament {tournament_id}: {e}")
            return {'matches': [], 'stats': {}}
            
    def get_tournament_players(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all players in a specific tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A list of dictionaries containing player data with tournament-specific info and team.
        """
        try:
            self.cursor.execute("""
                SELECT p.id, p.name, p.rating, p.team,
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
            
    def get_players(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all players in a tournament with their details.
        
        This is an alias for get_tournament_players for backward compatibility.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A list of dictionaries containing player data.
        """
        return self.get_tournament_players(tournament_id)
            
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
            
    def get_player_color_history(self, tournament_id: int, player_id: int) -> List[Dict[str, Any]]:
        """Get a player's color history in a tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player.
            
        Returns:
            A list of dictionaries containing round number and color ('white' or 'black') for each game.
        """
        try:
            query = """
            SELECT 
                r.round_number,
                CASE 
                    WHEN p.white_player_id = ? THEN 'white'
                    WHEN p.black_player_id = ? THEN 'black'
                END as color
            FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.tournament_id = ?
            AND (p.white_player_id = ? OR p.black_player_id = ?)
            AND p.status = 'completed'
            ORDER BY r.round_number
            """
            self.cursor.execute(query, (player_id, player_id, tournament_id, player_id, player_id))
            return [dict(row) for row in self.cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Error getting player color history: {e}")
            return []
            
    def get_player_history(self, player_id: int) -> List[Dict[str, Any]]:
        """Get a player's match history across all tournaments.
        
        Args:
            player_id: The ID of the player.
            
        Returns:
            A list of dictionaries containing match history with opponent, result, and tournament info.
        """
        try:
            print(f"Fetching history for player ID: {player_id}")
            
            # First, verify the player exists
            self.cursor.execute("SELECT id, name FROM players WHERE id = ?", (player_id,))
            player = self.cursor.fetchone()
            if not player:
                print(f"Player with ID {player_id} not found")
                return []
                
            print(f"Found player: {player['name']} (ID: {player['id']})")
            
            query = """
            SELECT 
                t.name as tournament_name,
                r.round_number,
                p1.name as white_name,
                p1.rating as white_rating,
                COALESCE(p2.name, 'BYE') as black_name,
                p2.rating as black_rating,
                COALESCE(p.result, '') as result,
                CASE 
                    WHEN p.white_player_id = ? THEN 'white'
                    WHEN p.black_player_id = ? THEN 'black'
                END as color,
                CASE 
                    WHEN p.white_player_id = ? AND p2.name IS NOT NULL THEN p2.name
                    WHEN p.white_player_id = ? AND p.black_player_id IS NULL THEN 'BYE'
                    WHEN p.black_player_id = ? THEN p1.name
                END as opponent_name,
                CASE
                    WHEN p.white_player_id = ? AND p2.rating IS NOT NULL THEN p2.rating
                    WHEN p.white_player_id = ? AND p.black_player_id IS NULL THEN NULL
                    WHEN p.black_player_id = ? THEN p1.rating
                END as opponent_rating,
                t.id as tournament_id,
                r.id as round_id,
                p.white_player_id,
                p.black_player_id,
                p.result as raw_result
            FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            JOIN tournaments t ON r.tournament_id = t.id
            JOIN players p1 ON p.white_player_id = p1.id
            LEFT JOIN players p2 ON p.black_player_id = p2.id
            WHERE (p.white_player_id = ? OR p.black_player_id = ?)
            ORDER BY t.start_date, t.id, r.round_number
            """
            
            params = (player_id, player_id, player_id, player_id, player_id, player_id, player_id, player_id, player_id, player_id)
            print(f"Executing query with params: {params}")
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            print(f"Found {len(rows)} matches for player {player_id}")
            
            if not rows:
                print("No matches found for player")
                # Let's check if the player exists in any tournaments
                self.cursor.execute("""
                    SELECT id FROM players WHERE id = ?
                    AND (EXISTS (SELECT 1 FROM pairings WHERE white_player_id = ?) 
                         OR EXISTS (SELECT 1 FROM pairings WHERE black_player_id = ?))
                """, (player_id, player_id, player_id))
                
                if not self.cursor.fetchone():
                    print("Player has no matches in any tournaments")
                else:
                    print("Player has matches but query returned no results - possible data inconsistency")
                
                return []
            
            history = []
            for row in rows:
                row_dict = dict(row)
                print(f"Processing match: {row_dict}")
                
                # Calculate points based on result and color
                result = row_dict['raw_result'] or ''
                color = row_dict['color']
                
                if result == '1-0':
                    points = 1.0 if color == 'white' else 0.0
                elif result == '0-1':
                    points = 1.0 if color == 'black' else 0.0
                elif result in ('½-½', '=', '0.5-0.5'):
                    points = 0.5
                else:
                    points = 0.0
                
                match_info = {
                    'round_number': row_dict['round_number'],
                    'opponent_name': row_dict['opponent_name'],
                    'opponent_rating': row_dict['opponent_rating'],
                    'color': color,
                    'result': result,
                    'points': points,
                    'tournament_id': row_dict['tournament_id'],
                    'tournament_name': row_dict['tournament_name']
                }
                print(f"Adding match to history: {match_info}")
                history.append(match_info)
                
            print(f"Returning {len(history)} matches for player {player_id}")
            return history
            
        except Exception as e:
            print(f"Error in get_player_history: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
            
    def get_player_bye_count(self, tournament_id: int, player_id: int) -> int:
        """Get the number of byes a player has received in the tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player.
            
        Returns:
            The number of byes the player has received.
        """
        try:
            self.cursor.execute("""
                SELECT COUNT(*) 
                FROM pairings p
                JOIN rounds r ON p.round_id = r.id
                WHERE r.tournament_id = ?
                AND p.white_player_id = ?
                AND p.black_player_id IS NULL
                AND p.status = 'completed'
            """, (tournament_id, player_id))
            
            return self.cursor.fetchone()[0] or 0
            
        except sqlite3.Error as e:
            print(f"Error getting player bye count: {e}")
            return 0
            
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
            
    def get_tournament_rounds(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all rounds for a tournament with their pairings.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A list of dictionaries containing round data with their pairings.
        """
        try:
            # First get all rounds for the tournament
            self.cursor.execute("""
                SELECT id, round_number, status, 
                       strftime('%Y-%m-%d %H:%M', start_time) as start_time,
                       strftime('%Y-%m-%d %H:%M', end_time) as end_time
                FROM rounds 
                WHERE tournament_id = ?
                ORDER BY round_number
            """, (tournament_id,))
            
            rounds = [dict(row) for row in self.cursor.fetchall()]
            
            # For each round, get its pairings
            for round_data in rounds:
                round_id = round_data['id']
                
                # Get pairings for this round
                self.cursor.execute("""
                    SELECT p.*, 
                           w.name as white_player_name, w.rating as white_rating,
                           b.name as black_player_name, b.rating as black_rating
                    FROM pairings p
                    LEFT JOIN players w ON p.white_player_id = w.id
                    LEFT JOIN players b ON p.black_player_id = b.id
                    WHERE p.round_id = ?
                    ORDER BY p.board_number
                """, (round_id,))
                
                pairings = [dict(row) for row in self.cursor.fetchall()]
                round_data['pairings'] = pairings
                
                # Get manual byes for this round
                self.cursor.execute("""
                    SELECT mb.*, p.name as player_name, p.rating as player_rating
                    FROM manual_byes mb
                    JOIN players p ON mb.player_id = p.id
                    WHERE mb.tournament_id = ? AND mb.round_number = ?
                """, (tournament_id, round_data['round_number']))
                
                # Add byes to pairings with is_bye flag
                byes = [dict(row) for row in self.cursor.fetchall()]
                for bye in byes:
                    pairings.append({
                        'id': f"bye_{bye['id']}",
                        'white_player_id': bye['player_id'],
                        'white_player_name': bye['player_name'],
                        'white_rating': bye['player_rating'],
                        'black_player_id': None,
                        'black_player_name': 'BYE',
                        'black_rating': None,
                        'result': '1-0',  # Default result for byes
                        'status': 'completed',
                        'is_bye': True,
                        'points_awarded': bye.get('points_awarded', 1.0)
                    })
                
                # Sort pairings to have byes first, then by board number
                round_data['pairings'].sort(key=lambda x: (0 if x.get('is_bye', False) else 1, 
                                                         x.get('board_number', 0)))
            
            return rounds
            
        except sqlite3.Error as e:
            print(f"Error getting tournament rounds: {e}")
            return []
            
    def get_manual_byes(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all manual byes for a tournament.
        
        Args:
            tournament_id: The ID of the tournament.
            
        Returns:
            A list of dictionaries containing bye information.
        """
        try:
            self.cursor.execute("""
                SELECT b.*, p.name as player_name
                FROM manual_byes b
                JOIN players p ON b.player_id = p.id
                WHERE b.tournament_id = ?
                ORDER BY b.round_number, p.name
            """, (tournament_id,))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting manual byes: {e}")
            return []
            
    def get_manual_bye(self, tournament_id: int, player_id: int, round_number: int) -> Optional[Dict[str, Any]]:
        """Check if a specific bye assignment exists.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player.
            round_number: The round number.
            
        Returns:
            The bye record if found, None otherwise.
        """
        try:
            self.cursor.execute("""
                SELECT * FROM manual_byes 
                WHERE tournament_id = ? AND player_id = ? AND round_number = ?
            """, (tournament_id, player_id, round_number))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting manual bye: {e}")
            return None
            
    def assign_manual_bye(self, tournament_id: int, player_id: int, round_number: int, created_by: int) -> bool:
        """Assign a manual bye to a player for a specific round.
        
        Args:
            tournament_id: The ID of the tournament.
            player_id: The ID of the player.
            round_number: The round number.
            created_by: The user ID who assigned the bye.
            
        Returns:
            bool: True if the bye was assigned successfully, False otherwise.
        """
        try:
            self.cursor.execute("""
                INSERT INTO manual_byes (tournament_id, player_id, round_number, created_by)
                VALUES (?, ?, ?, ?)
            """, (tournament_id, player_id, round_number, created_by))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error assigning manual bye: {e}")
            self.conn.rollback()
            return False
            
    def remove_manual_bye(self, bye_id: int) -> bool:
        """Remove a manual bye assignment.
        
        Args:
            bye_id: The ID of the bye assignment to remove.
            
        Returns:
            bool: True if the bye was removed successfully, False otherwise.
        """
        try:
            self.cursor.execute("DELETE FROM manual_byes WHERE id = ?", (bye_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error removing manual bye: {e}")
            self.conn.rollback()
            return False
            
    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Get a player by ID.
        
        Args:
            player_id: The ID of the player to retrieve.
            
        Returns:
            A dictionary containing the player data, or None if not found.
        """
        try:
            self.cursor.execute("SELECT * FROM players WHERE id = ?", (player_id,))
            result = self.cursor.fetchone()
            return dict(result) if result else None
            
        except sqlite3.Error as e:
            print(f"Error getting player {player_id}: {e}")
            return None
            
    def update_player(self, player_id: int, name: str, rating: int) -> bool:
        """Update a player's details.
        
        Args:
            player_id: The ID of the player to update.
            name: The new name for the player.
            rating: The new rating for the player.
            
        Returns:
            True if the update was successful, False otherwise.
        """
        try:
            self.cursor.execute(
                "UPDATE players SET name = ?, rating = ? WHERE id = ?",
                (name, rating, player_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
            
        except sqlite3.Error as e:
            print(f"Error updating player {player_id}: {e}")
            self.conn.rollback()
            return False
            
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
            # Start a transaction
            self.conn.execute('BEGIN TRANSACTION')
            
            # Get all players ordered by score and rating
            players = self.get_tournament_players_with_scores(tournament_id)
            
            # Check if there are enough players to generate pairings
            if not players:
                self.conn.rollback()
                return False
                
            # Ensure there are at least 2 players to generate pairings
            if len(players) < 2:
                self.conn.rollback()
                return False
                
            # Get the round number for tiebreak updates
            self.cursor.execute("SELECT round_number FROM rounds WHERE id = ?", (round_id,))
            round_result = self.cursor.fetchone()
            if not round_result:
                self.conn.rollback()
                return False
                
            round_number = round_result[0]
            
            # First, clear any existing pairings for this round to avoid duplicates
            self.cursor.execute("DELETE FROM pairings WHERE round_id = ?", (round_id,))
            
            # Get players with manual byes for this round
            self.cursor.execute("""
                SELECT player_id FROM manual_byes 
                WHERE tournament_id = ? AND round_number = ?
            """, (tournament_id, round_number))
            
            players_with_manual_byes = {row[0] for row in self.cursor.fetchall()}
            
            # Create a list of players who should be paired (excluding those with byes)
            players_to_pair = [p for p in players if p['id'] not in players_with_manual_byes]
            
            # For players with byes, create a bye pairing and award a point
            for player_id in players_with_manual_byes:
                player = next((p for p in players if p['id'] == player_id), None)
                if player:
                    # Get the next available board number
                    self.cursor.execute("""
                        SELECT COALESCE(MAX(board_number), 0) + 1 
                        FROM pairings 
                        WHERE round_id = ?
                    """, (round_id,))
                    next_board = self.cursor.fetchone()[0] or 1
                    
                    # Create the bye pairing - this will automatically award a point via create_pairing
                    self.create_pairing(round_id, player['id'], None, next_board)
                    
                    # Ensure the player has a tournament_players entry
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO tournament_players 
                        (tournament_id, player_id, initial_rating, score)
                        VALUES (?, ?, ?, 0)
                    """, (tournament_id, player_id, player.get('rating', 1200)))
            
            # Use the filtered list for the rest of the pairing logic
            players = players_to_pair
            
            # For the first round, pair by rating
            if round_number == 1:
                # Sort by rating for first round
                players.sort(key=lambda x: x['rating'], reverse=True)
                
                # Calculate the number of pairings needed
                num_pairings = len(players) // 2
                pairings = []
                
                # Pair top half with bottom half
                for i in range(num_pairings):
                    white_player = players[i]
                    black_player = players[num_pairings + i]
                    pairings.append((white_player, black_player))
                
                # If odd number of players, give a bye to the lowest-rated player
                if len(players) % 2 != 0 and not players_with_manual_byes:
                    bye_player = players[-1]
                    # Get the next available board number
                    self.cursor.execute("""
                        SELECT COALESCE(MAX(board_number), 0) + 1 
                        FROM pairings 
                        WHERE round_id = ?
                    """, (round_id,))
                    next_board = self.cursor.fetchone()[0] or 1
                    
                    self.create_pairing(round_id, bye_player['id'], None, next_board)
                    
            else:
                # For subsequent rounds, use Swiss system
                # Sort by score (descending), then rating (descending)
                players.sort(key=lambda x: (-x.get('score', 0), -x.get('rating', 0)))
                
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
                    
                    # Get player's color history for better balancing
                player1_history = self.get_player_color_history(tournament_id, player1['id'])
                player1_white_count = sum(1 for h in player1_history if h['color'] == 'white')
                player1_black_count = sum(1 for h in player1_history if h['color'] == 'black')
                
                # Try to find the highest-ranked opponent with the same or similar score
                for score_diff in [0, 0.5, 1.0, 1.5, 2.0]:
                    found_opponent = False
                    best_opponent = None
                    best_color_balance = float('inf')
                    
                    for j in range(i + 1, len(players)):
                        player2 = players[j]
                        
                        # Skip if already paired, score difference too big, or already played
                        if (player2['id'] in paired or 
                            abs(player2.get('score', 0) - player1.get('score', 0)) > score_diff or
                            player2['id'] in previous_opponents or
                            player2['id'] == player1['id']):
                            continue
                        
                        # Get opponent's color history
                        player2_history = self.get_player_color_history(tournament_id, player2['id'])
                        player2_white_count = sum(1 for h in player2_history if h['color'] == 'white')
                        player2_black_count = sum(1 for h in player2_history if h['color'] == 'black')
                        
                        # Try both color assignments and pick the one that balances colors better
                        # Option 1: player1 as white
                        option1_balance = abs((player1_white_count + 1 - player1_black_count) - 
                                            (player2_white_count - (player2_black_count + 1)))
                        
                        # Option 2: player2 as white
                        option2_balance = abs((player1_black_count + 1 - player1_white_count) - 
                                            (player2_white_count + 1 - player2_black_count))
                        
                        # Track the best color balance we can achieve
                        current_balance = min(option1_balance, option2_balance)
                        
                        if best_opponent is None or current_balance < best_color_balance:
                            best_opponent = player2
                            best_color_balance = current_balance
                            best_pairing = (player1, player2) if option1_balance <= option2_balance else (player2, player1)
                    
                    if best_opponent is not None:
                        pairings.append(best_pairing)
                        paired.add(player1['id'])
                        paired.add(best_opponent['id'])
                        found_opponent = True
                        break
                
                # Get all unpaired players
                unpaired = [p for p in players if p['id'] not in paired]
                
                # If we have an odd number of players, handle the bye
                if len(unpaired) % 2 != 0:
                    # First, try to pair the top players who haven't been paired yet
                    # This prevents giving byes to players who should be in title fights
                    if len(unpaired) >= 3:  # Need at least 3 players to make this meaningful
                        # Sort unpaired players by score (desc) and rating (desc)
                        unpaired_sorted = sorted(unpaired, 
                                              key=lambda x: (-x.get('score', 0), -x.get('rating', 0)))
                        
                        # Try to find a valid pairing among the top players
                        for i in range(len(unpaired_sorted)):
                            for j in range(i + 1, len(unpaired_sorted)):
                                player1 = unpaired_sorted[i]
                                player2 = unpaired_sorted[j]
                                
                                # Check if these players haven't played before
                                if (player2['id'] not in self.get_previous_pairings(tournament_id, player1['id'])):
                                    # Found a valid pairing, use it and remove from unpaired
                                    pairings.append((player1, player2))
                                    paired.add(player1['id'])
                                    paired.add(player2['id'])
                                    unpaired = [p for p in unpaired 
                                              if p['id'] not in {player1['id'], player2['id']}]
                                    print(f"Paired top players to avoid unnecessary bye: {player1.get('name')} vs {player2.get('name')}")
                                    break
                            else:
                                continue
                            break
                    
                    # If we still have an odd number after trying to pair top players
                    if len(unpaired) % 2 != 0:
                        # Find player with fewest byes (or lowest rating if tied)
                        # Exclude top players from bye consideration
                        eligible_for_bye = unpaired
                        if len(unpaired) > 1:  # If there are multiple players left
                            # Don't give byes to top players (top half of unpaired)
                            mid_point = len(unpaired) // 2
                            eligible_for_bye = unpaired[mid_point:]
                            
                        players_with_bye_counts = [
                            {
                                **p,
                                'bye_count': self.get_player_bye_count(tournament_id, p['id']),
                                'rating': p.get('rating', 0)
                            }
                            for p in eligible_for_bye
                        ]
                        
                        if not players_with_bye_counts:  # Fallback in case all players are top players
                            players_with_bye_counts = [
                                {
                                    **p,
                                    'bye_count': self.get_player_bye_count(tournament_id, p['id']),
                                    'rating': p.get('rating', 0)
                                }
                                for p in unpaired
                            ]
                        
                        # Sort by bye count (ascending) and then by rating (ascending)
                        players_with_bye_counts.sort(key=lambda x: (x['bye_count'], x['rating']))
                        
                        # The player with the fewest byes (and lowest rating if tied) gets the bye
                        bye_player = players_with_bye_counts[0]
                        
                        # Remove the player from unpaired and add to pairings
                        pairings.append((bye_player, None))
                        paired.add(bye_player['id'])
                        unpaired = [p for p in unpaired if p['id'] != bye_player['id']]
                        
                        # Add a message about the bye
                        print(f"Assigned bye to {bye_player.get('name', 'Unknown')} (Bye count: {bye_player['bye_count']})")
                
                # Pair remaining unpaired players (if any) with color balance in mind
                while len(unpaired) >= 2:
                    player1 = unpaired.pop(0)
                    
                    # Get color history for player1
                    player1_history = self.get_player_color_history(tournament_id, player1['id'])
                    player1_white = sum(1 for h in player1_history if h['color'] == 'white')
                    player1_black = sum(1 for h in player1_history if h['color'] == 'black')
                    
                    # Find the best opponent to balance colors
                    best_balance = float('inf')
                    best_opponent = None
                    best_pairing = None
                    
                    for j, player2 in enumerate(unpaired):
                        # Get color history for potential opponent
                        player2_history = self.get_player_color_history(tournament_id, player2['id'])
                        player2_white = sum(1 for h in player2_history if h['color'] == 'white')
                        player2_black = sum(1 for h in player2_history if h['color'] == 'black')
                        
                        # Calculate color balance for both possible pairings
                        # Option 1: player1 as white
                        option1_balance = abs((player1_white + 1 - player1_black) - 
                                           (player2_white - (player2_black + 1)))
                        
                        # Option 2: player2 as white
                        option2_balance = abs((player1_black + 1 - player1_white) - 
                                           (player2_white + 1 - player2_black))
                        
                        # Track the best balance
                        current_balance = min(option1_balance, option2_balance)
                        
                        if current_balance < best_balance:
                            best_balance = current_balance
                            best_opponent = j
                            best_pairing = (player1, player2) if option1_balance <= option2_balance else (player2, player1)
                    
                    # Add the best pairing found
                    if best_opponent is not None and best_pairing is not None:
                        pairings.append(best_pairing)
                        unpaired.pop(best_opponent)
                    else:
                        # Fallback to simple pairing if something went wrong
                        player2 = unpaired.pop(0)
                        if player1.get('rating', 0) >= player2.get('rating', 0):
                            pairings.append((player1, player2))
                        else:
                            pairings.append((player2, player1))
            
            # Create the pairings in the database
            board_number = 1
            for white, black in pairings:
                if black is not None:
                    # Regular pairing
                    self.create_pairing(round_id, white['id'], black['id'], board_number)
                else:
                    # Player with a bye - create a pairing with black_player_id as None
                    self.create_pairing(round_id, white['id'], None, board_number)
                board_number += 1
            
            # Update round status
            self.cursor.execute("""
                UPDATE rounds 
                SET status = 'in_progress', 
                    start_time = datetime('now')
                WHERE id = ?
            """, (round_id,))
            
            # Commit the transaction
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error in generate_pairings: {str(e)}")
            if self.conn:
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
            **kwargs: Additional tournament fields (location, time_control, status, created_at, share_token)
            
        Returns:
            int: ID of the created tournament
        """
        import secrets
        
        # Generate a unique share token if not provided
        share_token = kwargs.pop('share_token', None)
        if not share_token:
            share_token = secrets.token_urlsafe(16)
            
        query = """
        INSERT INTO tournaments (
            name, start_date, end_date, time_control, 
            rounds, status, location, created_at, creator_id, description,
            share_token
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            kwargs.get('description', ''),
            share_token
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
        try:
            query = """
            INSERT INTO rounds (tournament_id, round_number, start_time, status)
            VALUES (?, ?, datetime('now'), 'ongoing')
            """
            self.cursor.execute(query, (tournament_id, round_number))
            
            # If this is the first round, update tournament status to 'ongoing'
            if round_number == 1:
                self.cursor.execute(
                    "UPDATE tournaments SET status = 'ongoing' WHERE id = ? AND status = 'upcoming'",
                    (tournament_id,)
                )
                
            self.conn.commit()
            return self.cursor.lastrowid
            
        except Exception as e:
            print(f"Error starting round: {e}")
            self.conn.rollback()
            raise

    def complete_round(self, round_id: int) -> bool:
        """Mark a round as completed and update tournament status if needed."""
        try:
            # First, get the tournament_id from the round
            self.cursor.execute("SELECT tournament_id, round_number FROM rounds WHERE id = ?", (round_id,))
            result = self.cursor.fetchone()
            if not result:
                return False
                
            tournament_id, round_number = result
            
            # Update the round status
            query = """
            UPDATE rounds 
            SET status = 'completed', end_time = datetime('now')
            WHERE id = ?
            """
            self.cursor.execute(query, (round_id,))
            
            # Update tournament status based on rounds
            self._update_tournament_status(tournament_id)
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error completing round: {e}")
            self.conn.rollback()
            return False
        
    def delete_tournament(self, tournament_id: int, creator_id: int) -> bool:
        """
        Delete a tournament and all its related data.
        
        Args:
            tournament_id: The ID of the tournament to delete
            creator_id: The ID of the user attempting to delete (must be the creator)
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # First verify the user is the creator and the tournament exists
            self.cursor.execute(
                "SELECT id, creator_id FROM tournaments WHERE id = ?",
                (tournament_id,)
            )
            result = self.cursor.fetchone()
            
            if not result or result[1] != creator_id:
                return False
            
            # Start transaction
            self.cursor.execute("BEGIN TRANSACTION")
            
            try:
                # 1. Delete pairings results first
                self.cursor.execute("""
                    DELETE FROM pairings 
                    WHERE round_id IN (SELECT id FROM rounds WHERE tournament_id = ?)
                """, (tournament_id,))
                
                # 2. Delete manual byes
                self.cursor.execute(
                    "DELETE FROM manual_byes WHERE tournament_id = ?",
                    (tournament_id,)
                )
                
                # 3. Delete rounds
                self.cursor.execute(
                    "DELETE FROM rounds WHERE tournament_id = ?",
                    (tournament_id,)
                )
                
                # 4. Delete tournament players
                self.cursor.execute(
                    "DELETE FROM tournament_players WHERE tournament_id = ?",
                    (tournament_id,)
                )
                
                # 5. Delete admin share links
                self.cursor.execute(
                    "DELETE FROM admin_share_links WHERE tournament_id = ?",
                    (tournament_id,)
                )
                
                # 6. Delete the tournament
                self.cursor.execute(
                    "DELETE FROM tournaments WHERE id = ?",
                    (tournament_id,)
                )
                
                self.conn.commit()
                return True
                
            except Exception as e:
                self.conn.rollback()
                print(f"Error in transaction while deleting tournament {tournament_id}: {e}")
                return False
            
        except Exception as e:
            print(f"Error preparing to delete tournament {tournament_id}: {e}")
            if 'self.conn' in locals() and self.conn:
                self.conn.rollback()
            return False
            
    def is_tournament_complete(self, tournament_id: int) -> bool:
        """Check if a tournament is complete (all rounds finished with results)."""
        # Get tournament info
        self.cursor.execute("""
            SELECT t.rounds, COUNT(r.id) as completed_rounds
            FROM tournaments t
            LEFT JOIN rounds r ON t.id = r.tournament_id AND r.status = 'completed'
            WHERE t.id = ?
            GROUP BY t.id, t.rounds
        """, (tournament_id,))
        
        result = self.cursor.fetchone()
        if not result or result[0] == 0:  # No rounds configured or no tournament found
            return False
            
        total_rounds, completed_rounds = result
        
        # Check if all rounds are completed
        if completed_rounds < total_rounds:
            return False
            
        # Check if all pairings have results
        self.cursor.execute("""
            SELECT COUNT(*) 
            FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.tournament_id = ? 
            AND p.result IS NULL 
            AND p.black_player_id IS NOT NULL
        """, (tournament_id,))
        
        incomplete_pairings = self.cursor.fetchone()[0]
        return incomplete_pairings == 0
        
    def _update_tournament_status(self, tournament_id: int):
        """Update the tournament status based on its rounds and pairings.
        
        Status can be:
        - 'upcoming': No rounds started yet
        - 'ongoing': At least one round has started
        - 'completed': Only set when explicitly concluded via the conclude_tournament endpoint
        """
        # Check if we need to update from 'upcoming' to 'ongoing'
        self.cursor.execute("""
            SELECT 1 FROM rounds 
            WHERE tournament_id = ? AND status = 'ongoing'
            LIMIT 1
        """, (tournament_id,))
        
        has_ongoing_round = self.cursor.fetchone() is not None
        
        # If there are any ongoing or completed rounds, mark as ongoing
        if has_ongoing_round:
            self.cursor.execute("""
                UPDATE tournaments 
                SET status = 'ongoing' 
                WHERE id = ? AND status = 'upcoming'
            """, (tournament_id,))

    # Reporting
    def get_players_with_bye_requests(self, tournament_id: int, round_number: int) -> List[Dict[str, Any]]:
        """Get players who have requested a bye for a specific round.
        
        Args:
            tournament_id: The ID of the tournament
            round_number: The round number to check for bye requests
            
        Returns:
            A list of dictionaries containing player data for those who requested a bye
        """
        try:
            self.cursor.execute("""
                SELECT p.id as player_id, p.name, p.rating
                FROM players p
                JOIN manual_byes mb ON p.id = mb.player_id
                WHERE mb.tournament_id = ? 
                AND mb.round_number = ?
            """, (tournament_id, round_number))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting players with bye requests: {e}")
            return []

    def get_round(self, round_id: int) -> Optional[Dict[str, Any]]:
        """Get a single round by its ID.
        
        Args:
            round_id: ID of the round to fetch
            
        Returns:
            Dictionary with round details or None if not found
        """
        try:
            self.cursor.execute("""
                SELECT id, tournament_id, round_number, status, 
                       start_time, end_time
                FROM rounds
                WHERE id = ?
            """, (round_id,))
            
            row = self.cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            print(f"Error getting round {round_id}: {e}")
            return None
            
    def get_rounds(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get all rounds for a tournament.
        
        Args:
            tournament_id: ID of the tournament
            
        Returns:
            List of rounds with their details
        """
        try:
            self.cursor.execute("""
                SELECT id, tournament_id, round_number, status, 
                       start_time, end_time
                FROM rounds
                WHERE tournament_id = ?
                ORDER BY round_number
            """, (tournament_id,))
            
            rounds = []
            for row in self.cursor.fetchall():
                rounds.append(dict(row))
                
            return rounds
            
        except Exception as e:
            print(f"Error getting rounds for tournament {tournament_id}: {e}")
            return []
            
    def get_player_standings(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get player standings for a tournament.
        
        Args:
            tournament_id: ID of the tournament
            
        Returns:
            List of player standings with scores and tiebreaks
        """
        return self.get_standings(tournament_id, 'individual')
    
    def get_team_standings(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Get current tournament standings grouped by team using the tournament's scoring system.
        
        Args:
            tournament_id: ID of the tournament
            
        Returns:
            List of team standings with scores and player details
        """
        # Get tournament point settings first
        self.cursor.execute("""
            SELECT win_points, draw_points, loss_points, bye_points
            FROM tournaments
            WHERE id = ?
        """, (tournament_id,))
        point_settings = self.cursor.fetchone()
        
        # Default point values if not set
        win_pts = float(point_settings['win_points']) if point_settings and point_settings['win_points'] is not None else 1.0
        draw_pts = float(point_settings['draw_points']) if point_settings and point_settings['draw_points'] is not None else 0.5
        loss_pts = float(point_settings['loss_points']) if point_settings and point_settings['loss_points'] is not None else 0.0
        bye_pts = float(point_settings['bye_points']) if point_settings and point_settings['bye_points'] is not None else 1.0
        
        # Get team standings with player details
        query = """
        WITH player_matches AS (
            SELECT 
                p.id as player_id,
                p.name as player_name,
                p.team,
                pr.id as pairing_id,
                pr.white_player_id,
                pr.black_player_id,
                pr.result,
                pr.status,
                CASE 
                    WHEN pr.white_player_id = p.id AND pr.result = '1-0' THEN ?  -- Win as white
                    WHEN pr.black_player_id = p.id AND pr.result = '0-1' THEN ?  -- Win as black
                    WHEN pr.white_player_id = p.id AND pr.result = '0-1' THEN ?  -- Loss as white
                    WHEN pr.black_player_id = p.id AND pr.result = '1-0' THEN ?  -- Loss as black
                    WHEN pr.result = '0.5-0.5' THEN ?  -- Draw
                    WHEN pr.status = 'bye' THEN ?  -- Bye
                    ELSE 0
                END as points_earned,
                CASE 
                    WHEN (pr.white_player_id = p.id AND pr.result = '1-0') OR 
                         (pr.black_player_id = p.id AND pr.result = '0-1') THEN 1  -- Win
                    ELSE 0
                END as is_win,
                CASE 
                    WHEN (pr.white_player_id = p.id AND pr.result = '0-1') OR 
                         (pr.black_player_id = p.id AND pr.result = '1-0') THEN 1  -- Loss
                    ELSE 0
                END as is_loss,
                CASE 
                    WHEN pr.result = '0.5-0.5' THEN 1  -- Draw
                    ELSE 0
                END as is_draw,
                CASE 
                    WHEN pr.status = 'bye' THEN 1  -- Bye
                    ELSE 0
                END as is_bye
            FROM players p
            JOIN tournament_players tp ON p.id = tp.player_id
            LEFT JOIN pairings pr ON (pr.white_player_id = p.id OR pr.black_player_id = p.id) 
                                  AND pr.status = 'completed'
            LEFT JOIN rounds r ON pr.round_id = r.id
            WHERE tp.tournament_id = ?
            AND p.team IS NOT NULL AND p.team != ''
        ),
        player_stats AS (
            SELECT 
                player_id,
                player_name,
                team,
                SUM(points_earned) as points,
                SUM(is_win) as wins,
                SUM(is_loss) as losses,
                SUM(is_draw) as draws,
                SUM(is_bye) as byes
            FROM player_matches
            GROUP BY player_id, player_name, team
        )
        SELECT 
            team,
            COUNT(DISTINCT player_id) as player_count,
            SUM(points) as total_points,
            SUM(wins) as match_wins,
            SUM(losses) as match_losses,
            SUM(draws) as match_draws,
            SUM(byes) as byes,
            ROUND(SUM(points) * 1.0 / COUNT(DISTINCT player_id), 2) as avg_points_per_player,
            GROUP_CONCAT(player_name || ' (' || ROUND(points, 2) || ' pts)', ', ') as player_details
        FROM player_stats
        WHERE team IS NOT NULL AND team != ''
        GROUP BY team
        ORDER BY 
            SUM(points) DESC,
            COUNT(DISTINCT player_id) DESC,
            ROUND(SUM(points) * 1.0 / COUNT(DISTINCT player_id), 2) DESC
        """
        
        # Pass point values as parameters - order is important for the CASE statement
        params = (
            win_pts,   # Win as white
            win_pts,   # Win as black
            loss_pts,  # Loss as white
            loss_pts,  # Loss as black
            draw_pts,  # Draw
            bye_pts,   # Bye
            tournament_id
        )
        
        try:
            self.cursor.execute(query, params)
            
            standings = []
            for i, row in enumerate(self.cursor.fetchall(), 1):
                standings.append({
                    'position': i,
                    'name': row['team'],
                    'total_points': float(row['total_points'] or 0),
                    'player_count': row['player_count'],
                    'avg_points_per_player': float(row['avg_points_per_player'] or 0),
                    'match_wins': int(row['match_wins'] or 0),
                    'match_losses': int(row['match_losses'] or 0),
                    'match_draws': int(row['match_draws'] or 0),
                    'byes': int(row['byes'] or 0),
                    'player_details': row['player_details'] or ''
                })
            
            return standings
            
        except sqlite3.Error as e:
            print(f"Error getting team standings: {e}")
            return []

    def get_standings(self, tournament_id: int, view_type: str = 'individual') -> List[Dict[str, Any]]:
        """Get current tournament standings with all required fields for the standings page.
        
        Args:
            tournament_id: ID of the tournament
            view_type: Either 'individual' or 'team' to specify the type of standings to return
            
        Returns:
            List of dictionaries containing player or team standings
        """
        if view_type == 'team':
            return self.get_team_standings(tournament_id)
            
        # Get all players who have ever been in the tournament
        query = """
        SELECT DISTINCT p.id, p.name, p.rating, p.team,
               CASE WHEN tp2.player_id IS NOT NULL THEN 1 ELSE 0 END as is_active
        FROM (
            -- Current tournament players
            SELECT player_id FROM tournament_players WHERE tournament_id = ?
            UNION
            -- Players who were in pairings but may have been removed
            SELECT DISTINCT white_player_id as player_id FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.tournament_id = ?
            UNION
            SELECT DISTINCT black_player_id as player_id FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.tournament_id = ? AND black_player_id IS NOT NULL
        ) all_players
        JOIN players p ON all_players.player_id = p.id
        LEFT JOIN tournament_players tp2 ON p.id = tp2.player_id AND tp2.tournament_id = ?
        """
        self.cursor.execute(query, (tournament_id, tournament_id, tournament_id, tournament_id))
        players = [dict(row) for row in self.cursor.fetchall()]
        
        # Get all pairings for this tournament, including unplayed ones
        query = """
        SELECT 
            pr.white_player_id, 
            pr.black_player_id, 
            pr.result,
            r.round_number,
            CASE WHEN pr.result IS NULL THEN 0 ELSE 1 END as is_completed
        FROM pairings pr
        JOIN rounds r ON pr.round_id = r.id
        WHERE r.tournament_id = ?
        """
        self.cursor.execute(query, (tournament_id,))
        pairings = self.cursor.fetchall()
        
        # Get tournament point settings
        query = """
        SELECT win_points, draw_points, loss_points, bye_points
        FROM tournaments
        WHERE id = ?
        """
        self.cursor.execute(query, (tournament_id,))
        point_settings = self.cursor.fetchone()
        
        # Default point values if not set
        win_pts = float(point_settings['win_points']) if point_settings and point_settings['win_points'] is not None else 1.0
        draw_pts = float(point_settings['draw_points']) if point_settings and point_settings['draw_points'] is not None else 0.5
        loss_pts = float(point_settings['loss_points']) if point_settings and point_settings['loss_points'] is not None else 0.0
        bye_pts = float(point_settings['bye_points']) if point_settings and point_settings['bye_points'] is not None else 1.0
        
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
            is_completed = pairing['is_completed']
            is_bye = black_id is None
            
            # Handle bye pairings (where black_player_id is NULL)
            if is_bye and white_id in player_map:
                white = player_map[white_id]
                # For byes, award points based on tournament settings
                if is_completed:
                    white['wins'] += 1
                    white['points'] += bye_pts  # Use configured bye points
                    white['games_played'] += 1
                # Record a dummy opponent for tiebreak purposes
                white['opponents'].append(None)  # Will be handled in tiebreak calculations
                
            # Handle regular pairings
            elif white_id in player_map and black_id in player_map:
                white = player_map[white_id]
                black = player_map[black_id]
                
                # Always record opponents for tiebreaks, even if game not completed
                white['opponents'].append(black_id)
                black['opponents'].append(white_id)
                
                # Only update games played and results if the game is completed
                if is_completed:
                    # Update games played
                    white['games_played'] += 1
                    black['games_played'] += 1
                    
                    # Update results using tournament point settings
                    if result == '1-0':
                        white['wins'] += 1
                        white['points'] += win_pts
                        black['losses'] += 1
                        black['points'] += loss_pts
                    elif result == '0-1':
                        black['wins'] += 1
                        black['points'] += win_pts
                        white['losses'] += 1
                        white['points'] += loss_pts
                    elif result == '0.5-0.5':
                        white['draws'] += 1
                        black['draws'] += 1
                        white['points'] += draw_pts
                        black['points'] += draw_pts
        
        # Calculate tiebreaks (Buchholz, etc.)
        for player in players:
            # Calculate performance rating (simplified)
            total_games = player['wins'] + player['losses'] + player['draws']
            if total_games > 0:
                player['performance'] = round((player['wins'] + (player['draws'] * 0.5)) / total_games * 100)
            
            # Calculate Buchholz (sum of opponents' scores from completed games only)
            buchholz = 0.0
            # Only consider opponents from completed games
            completed_opponents = []
            for i, opp_id in enumerate(player['opponents']):
                # Skip None (which represents a bye in the opponents list)
                if opp_id is None:
                    # Count a bye as half the average points in the tournament for tiebreak purposes
                    # This is a common approach to handle byes in tiebreaks
                    avg_points = sum(p['points'] for p in players) / max(1, len(players))
                    buchholz += avg_points * 0.5  # Half the average points for a bye
                    continue
                    
                if opp_id in player_map and player['games_played'] > i:
                    completed_opponents.append(opp_id)
            
            # Calculate Buchholz only for completed games
            for opp_id in completed_opponents:
                if opp_id in player_map:
                    # Only count points from completed games for the opponent as well
                    opp = player_map[opp_id]
                    buchholz += opp['points']
            
            player['buchholz'] = buchholz
            
            # Calculate Sonneborn-Berger score (sum of scores of opponents the player has beaten or drawn with)
            sb_score = 0.0
            for i, opp_id in enumerate(completed_opponents):
                if i >= player['games_played']:
                    continue
                if opp_id in player_map:
                    # Only add points for wins and draws
                    result = None
                    # Find the result against this opponent
                    for pairing in pairings:
                        if (pairing['white_player_id'] == player['id'] and pairing['black_player_id'] == opp_id and pairing['is_completed']) or \
                           (pairing['black_player_id'] == player['id'] and pairing['white_player_id'] == opp_id and pairing['is_completed']):
                            result = pairing['result']
                            break
                    
                    if result:
                        if player['id'] == pairing['white_player_id']:
                            if result == '1-0':
                                sb_score += player_map[opp_id]['points']
                            elif result == '0.5-0.5':
                                sb_score += player_map[opp_id]['points'] * 0.5
                        else:  # player is black
                            if result == '0-1':
                                sb_score += player_map[opp_id]['points']
                            elif result == '0.5-0.5':
                                sb_score += player_map[opp_id]['points'] * 0.5
            
            player['sonneborn_berger'] = sb_score
            
            # Add trend (same as performance for now)
            player['trend'] = player['performance']
            
            # Add tiebreak fields for sorting
            player['tiebreak1'] = player['points']  # Primary sort by points
            player['tiebreak2'] = buchholz  # Secondary sort by Buchholz
            player['tiebreak3'] = player.get('sonneborn_berger', 0)  # Tertiary sort by Sonneborn-Berger
            player['tiebreak4'] = player['performance']  # Quaternary sort by performance
        
        # Add status to each player
        for player in players:
            player['status'] = 'active' if player.get('is_active', 1) else 'withdrawn'
            
        # Sort standings - active players first, then by points and tiebreaks
        standings = sorted(
            players, 
            key=lambda x: (
                0 if x.get('is_active', 1) else 1,  # Active players first
                -x['points'],  # Primary: Points
                -x['buchholz'],  # Secondary: Buchholz
                -x.get('sonneborn_berger', 0),  # Tertiary: Sonneborn-Berger
                -x['performance'],  # Quaternary: Performance
                -x['rating']  # Quinary: Rating
            )
        )
        
        return standings

    def get_pairings(self, round_id: int) -> List[Dict[str, Any]]:
        """Get all pairings for a round, including byes."""
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
            b.rating as black_rating,
            CASE WHEN p.black_player_id IS NULL THEN 1 ELSE 0 END as is_bye
        FROM pairings p
        LEFT JOIN players w ON p.white_player_id = w.id
        LEFT JOIN players b ON p.black_player_id = b.id
        WHERE p.round_id = ?
        ORDER BY 
            CASE WHEN p.black_player_id IS NULL THEN 1 ELSE 0 END,  -- Show byes first
            p.board_number
        """
        self.cursor.execute(query, (round_id,))
        pairings = []
        for row in self.cursor.fetchall():
            pairing = dict(row)
            # For bye pairings, ensure the black player info is None
            if pairing['black_player_id'] is None:
                pairing.update({
                    'black_name': None,
                    'black_rating': None
                })
            pairings.append(pairing)
        return pairings

    def is_current_round_complete(self, tournament_id: int) -> bool:
        """Check if all results are in for the current round.
        
        Args:
            tournament_id: The ID of the tournament
            
        Returns:
            bool: True if all current round results are in, False otherwise
        """
        # Get current round
        current_round = self.get_current_round(tournament_id)
        if not current_round:
            return False
            
        # Get all pairings for current round
        pairings = self.get_pairings(current_round['id'])
        if not pairings:
            return False
            
        # Check if all pairings have results
        return all(p['result'] is not None for p in pairings)

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
