from collections import defaultdict
import random

class SwissPairing:
    def __init__(self, tournament_db):
        self.db = tournament_db

    def _get_players_by_score(self, tournament_id):
        """Group players by their current score"""
        players = self.db.get_tournament_players(tournament_id)
        score_groups = defaultdict(list)
        
        for player in players:
            score = player[5]  # score is at index 5
            score_groups[score].append(player)
            
        # Sort each score group by rating (descending)
        for score in score_groups:
            score_groups[score].sort(key=lambda x: x[4], reverse=True)  # rating is at index 4
            
        return score_groups

    def _can_pair(self, player1, player2, previous_pairings):
        """Check if two players can be paired"""
        # Check if they've played before
        player1_id = player1[0]  # player id is at index 0
        player2_id = player2[0]
        
        if player1_id == player2_id:
            return False
            
        # Check if they've played before
        if player1_id in previous_pairings and player2_id in previous_pairings[player1_id]:
            return False
            
        if player2_id in previous_pairings and player1_id in previous_pairings[player2_id]:
            return False
            
        return True

    def _get_previous_pairings(self, tournament_id):
        """Get a dictionary of previous pairings"""
        rounds = self.db.get_tournament_rounds(tournament_id)
        pairings = {}
        
        for round_ in rounds:
            round_id = round_[0]
            round_pairings = self.db.get_round_pairings(round_id)
            
            for pairing in round_pairings:
                white_id = pairing[2]  # white_player_id
                black_id = pairing[3]  # black_player_id
                
                if white_id not in pairings:
                    pairings[white_id] = set()
                if black_id not in pairings:
                    pairings[black_id] = set()
                    
                pairings[white_id].add(black_id)
                pairings[black_id].add(white_id)
                
        return pairings

    def _get_color_preference(self, player_id, tournament_id):
        """Determine player's color preference for this round"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
        SELECT 
            SUM(CASE WHEN white_player_id = ? THEN 1 ELSE 0 END) as white_count,
            SUM(CASE WHEN black_player_id = ? THEN 1 ELSE 0 END) as black_count
        FROM pairings p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.tournament_id = ?
        ''', (player_id, player_id, tournament_id))
        
        white_count, black_count = cursor.fetchone() or (0, 0)
        
        if white_count < black_count:
            return 'white'
        elif black_count < white_count:
            return 'black'
        else:
            return None  # No preference

    def _try_pair_players(self, players, previous_pairings, tournament_id):
        """Try to pair players using the Dutch pairing system"""
        paired = set()
        pairings = []
        
        # Sort players by rating (descending)
        players_sorted = sorted(players, key=lambda x: x[4], reverse=True)
        
        while players_sorted:
            player1 = players_sorted.pop(0)
            
            if player1[0] in paired:
                continue
                
            paired.add(player1[0])
            player1_id = player1[0]
            
            # Try to find an opponent
            opponent = None
            color_pref = self._get_color_preference(player1_id, tournament_id)
            
            # Try to find an opponent with the same score
            for i, player2 in enumerate(players_sorted):
                player2_id = player2[0]
                
                if player2_id in paired:
                    continue
                    
                if self._can_pair(player1, player2, previous_pairings):
                    # Check color preferences
                    if color_pref == 'white':
                        pairings.append((player1, player2, 'white'))
                    elif color_pref == 'black':
                        pairings.append((player2, player1, 'black'))
                    else:
                        # No preference, alternate colors
                        if len(paired) % 2 == 0:
                            pairings.append((player1, player2, 'white'))
                        else:
                            pairings.append((player2, player1, 'black'))
                            
                    paired.add(player2_id)
                    del players_sorted[i]
                    opponent = player2
                    break
            
            # If no opponent found, mark as bye if needed
            if not opponent and len(players_sorted) % 2 == 1:
                pairings.append((player1, None, 'bye'))
                
        return pairings

    def generate_pairings(self, tournament_id):
        """Generate pairings for the next round"""
        # Get current tournament info
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT current_round, rounds FROM tournaments WHERE id = ?', (tournament_id,))
        current_round, total_rounds = cursor.fetchone()
        
        if current_round >= total_rounds:
            return None, "Tournament is already complete"
            
        # Check if current round is complete
        cursor.execute('''
        SELECT COUNT(*) FROM pairings p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.tournament_id = ? AND r.round_number = ? AND p.result = '*'
        ''', (tournament_id, current_round))
        
        pending_games = cursor.fetchone()[0]
        
        if pending_games > 0 and current_round > 0:
            return None, f"There are still {pending_games} games pending in the current round"
        
        # Get all players grouped by score
        score_groups = self._get_players_by_score(tournament_id)
        
        # Get previous pairings to avoid rematches
        previous_pairings = self._get_previous_pairings(tournament_id)
        
        # Create new round
        new_round_num = current_round + 1
        round_id = self.db.create_round(tournament_id, new_round_num)
        
        # Generate pairings for each score group
        all_pairings = []
        board_number = 1
        
        # Process score groups from highest to lowest
        for score in sorted(score_groups.keys(), reverse=True):
            players = score_groups[score]
            
            # If odd number of players, handle the bye
            if len(players) % 2 != 0:
                # Find a player who hasn't had a bye yet
                for i, player in enumerate(players):
                    player_id = player[0]
                    cursor.execute('''
                    SELECT COUNT(*) FROM pairings 
                    WHERE (white_player_id = ? OR black_player_id = ?) AND result = 'bye'
                    ''', (player_id, player_id))
                    
                    if cursor.fetchone()[0] == 0:
                        # This player gets the bye
                        bye_player = players.pop(i)
                        all_pairings.append((bye_player, None, 'bye'))
                        break
                
                # If no player found without a bye, give it to the lowest rated player
                if len(players) % 2 != 0:
                    bye_player = players.pop()
                    all_pairings.append((bye_player, None, 'bye'))
            
            # Pair remaining players in this score group
            if players:
                pairings = self._try_pair_players(players, previous_pairings, tournament_id)
                all_pairings.extend(pairings)
        
        # Save pairings to database
        for white, black, color in all_pairings:
            if color == 'bye':
                # Record bye
                self.db.create_pairing(round_id, white[0], None, 0)
                self.db.record_result(round_id, '1-0')  # Typically, a bye is a win
                self.db.update_player_score(white[0], 1.0)
            else:
                if color == 'white':
                    self.db.create_pairing(round_id, white[0], black[0], board_number)
                else:
                    self.db.create_pairing(round_id, black[0], white[0], board_number)
                board_number += 1
        
        # Update tournament current round
        cursor.execute('''
        UPDATE tournaments 
        SET current_round = ?
        WHERE id = ?
        ''', (new_round_num, tournament_id))
        
        self.db.conn.commit()
        
        return all_pairings, f"Pairings generated for round {new_round_num}"

    def record_result(self, pairing_id, result):
        """Record the result of a game"""
        cursor = self.db.conn.cursor()
        
        # Get the pairing details
        cursor.execute('''
        SELECT white_player_id, black_player_id, round_id 
        FROM pairings 
        WHERE id = ?
        ''', (pairing_id,))
        
        white_id, black_id, round_id = cursor.fetchone()
        
        # Update the result
        self.db.record_result(pairing_id, result)
        
        # Update player scores
        if result == '1-0':
            self.db.update_player_score(white_id, 1.0)
            self.db.update_player_score(black_id, 0.0)
        elif result == '0-1':
            self.db.update_player_score(white_id, 0.0)
            self.db.update_player_score(black_id, 1.0)
        elif result == '1/2-1/2':
            self.db.update_player_score(white_id, 0.5)
            self.db.update_player_score(black_id, 0.5)
        elif result == 'bye':
            # Already handled in generate_pairings
            pass
            
        self.db.conn.commit()
        
        # Check if round is complete
        cursor.execute('''
        SELECT COUNT(*) FROM pairings 
        WHERE round_id = ? AND result = '*'
        ''', (round_id,))
        
        pending_games = cursor.fetchone()[0]
        
        if pending_games == 0:
            # Update round status to completed
            cursor.execute('''
            UPDATE rounds 
            SET status = 'completed', end_time = datetime('now')
            WHERE id = ?
            ''', (round_id,))
            
            # Check if tournament is complete
            cursor.execute('''
            SELECT current_round, rounds FROM tournaments t
            JOIN rounds r ON t.id = r.tournament_id
            WHERE r.id = ?
            ''', (round_id,))
            
            current_round, total_rounds = cursor.fetchone()
            
            if current_round >= total_rounds:
                cursor.execute('''
                UPDATE tournaments 
                SET status = 'completed'
                WHERE id = (SELECT tournament_id FROM rounds WHERE id = ?)
                ''', (round_id,))
                
            self.db.conn.commit()
            
        return "Result recorded successfully"
