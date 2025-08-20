from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from tournament_db import TournamentDB
from pairing_algorithm import SwissPairing
import os

# Initialize database and pairing system
db = TournamentDB('instance/tournament.db')
pairing_system = SwissPairing(db)

tournament_bp = Blueprint('tournament', __name__, url_prefix='/tournament')

@tournament_bp.route('/')
def index():
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    # Get all tournaments
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM tournaments ORDER BY created_at DESC')
    tournaments = cursor.fetchall()
    
    return render_template('tournament/index.html', tournaments=tournaments)

@tournament_bp.route('/create', methods=['GET', 'POST'])
def create():
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        rounds = int(request.form.get('rounds', 5))
        
        if not name:
            flash('Tournament name is required', 'error')
            return redirect(request.url)
        
        # Create tournament
        tournament_id = db.create_tournament(name, rounds)
        flash('Tournament created successfully!', 'success')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    return render_template('tournament/create.html')

@tournament_bp.route('/<int:tournament_id>')
def view(tournament_id):
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    # Get tournament details
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
    tournament = cursor.fetchone()
    
    if not tournament:
        flash('Tournament not found', 'error')
        return redirect(url_for('tournament.index'))
    
    # Get players
    players = db.get_tournament_players(tournament_id)
    
    # Get rounds
    rounds = db.get_tournament_rounds(tournament_id)
    current_round = tournament[5]  # current_round is at index 5
    
    # Get pairings for the current round if it exists
    current_round_pairings = []
    if current_round > 0:
        cursor.execute('''
        SELECT p.*, wp.name as white_name, bp.name as black_name
        FROM pairings p
        JOIN players wp ON p.white_player_id = wp.id
        LEFT JOIN players bp ON p.black_player_id = bp.id
        JOIN rounds r ON p.round_id = r.id
        WHERE r.tournament_id = ? AND r.round_number = ?
        ORDER BY p.board_number
        ''', (tournament_id, current_round))
        current_round_pairings = cursor.fetchall()
    
    # Get standings
    cursor.execute('''
    SELECT id, name, rating, score, 
           (SELECT COUNT(*) FROM pairings p 
            JOIN rounds r ON p.round_id = r.id 
            WHERE (p.white_player_id = players.id OR p.black_player_id = players.id) 
            AND r.tournament_id = ?) as games_played
    FROM players 
    WHERE tournament_id = ?
    ORDER BY score DESC, rating DESC
    ''', (tournament_id, tournament_id))
    
    standings = cursor.fetchall()
    
    return render_template('tournament/view.html', 
                         tournament=tournament, 
                         players=players,
                         rounds=rounds,
                         current_round=current_round,
                         current_round_pairings=current_round_pairings,
                         standings=standards)

@tournament_bp.route('/<int:tournament_id>/add_player', methods=['POST'])
def add_player(tournament_id):
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name')
    rating = int(request.form.get('rating', 0))
    
    if not name:
        flash('Player name is required', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    db.add_player(tournament_id, name, rating)
    flash('Player added successfully!', 'success')
    return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/generate_pairings', methods=['POST'])
def generate_pairings(tournament_id):
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    # Check if tournament exists and is not completed
    cursor = db.conn.cursor()
    cursor.execute('SELECT status, current_round, rounds FROM tournaments WHERE id = ?', (tournament_id,))
    tournament = cursor.fetchone()
    
    if not tournament:
        flash('Tournament not found', 'error')
        return redirect(url_for('tournament.index'))
    
    if tournament[0] == 'completed':
        flash('Tournament is already completed', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    # Generate pairings
    pairings, message = pairing_system.generate_pairings(tournament_id)
    
    if not pairings:
        flash(message, 'error')
    else:
        flash(message, 'success')
    
    return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/pairing/<int:pairing_id>/record_result', methods=['POST'])
def record_result(pairing_id):
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    result = request.form.get('result')
    
    if result not in ['1-0', '0-1', '1/2-1/2']:
        flash('Invalid result', 'error')
        return redirect(request.referrer)
    
    # Get tournament_id for redirect
    cursor = db.conn.cursor()
    cursor.execute('''
    SELECT t.id FROM tournaments t
    JOIN rounds r ON t.id = r.tournament_id
    JOIN pairings p ON r.id = p.round_id
    WHERE p.id = ?
    ''', (pairing_id,))
    
    tournament_id = cursor.fetchone()[0]
    
    # Record result
    pairing_system.record_result(pairing_id, result)
    flash('Result recorded successfully!', 'success')
    return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/standings')
def standings(tournament_id):
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    # Get tournament details
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
    tournament = cursor.fetchone()
    
    if not tournament:
        flash('Tournament not found', 'error')
        return redirect(url_for('tournament.index'))
    
    # Get standings with tiebreaks
    cursor.execute('''
    WITH player_games AS (
        SELECT 
            p.id as player_id,
            p.name as player_name,
            p.rating,
            p.score,
            COUNT(*) as games_played,
            SUM(CASE 
                WHEN (p2.white_player_id = p.id AND p2.result = '1-0') OR 
                     (p2.black_player_id = p.id AND p2.result = '0-1') THEN 1
                WHEN p2.result = '1/2-1/2' THEN 0.5
                ELSE 0
            END) as wins,
            SUM(CASE 
                WHEN p2.white_player_id = p.id THEN 
                    (SELECT score FROM players WHERE id = p2.black_player_id)
                WHEN p2.black_player_id = p.id THEN
                    (SELECT score FROM players WHERE id = p2.white_player_id)
                ELSE 0
            END) as buchholz
        FROM players p
        LEFT JOIN pairings p2 ON p.id = p2.white_player_id OR p.id = p2.black_player_id
        WHERE p.tournament_id = ?
        GROUP BY p.id, p.name, p.rating, p.score
    )
    SELECT 
        player_id,
        player_name,
        rating,
        score,
        games_played,
        wins,
        buchholz,
        RANK() OVER (ORDER BY score DESC, buchholz DESC, rating DESC) as rank
    FROM player_games
    ORDER BY rank
    ''', (tournament_id,))
    
    standings = cursor.fetchall()
    
    return render_template('tournament/standings.html', 
                         tournament=tournament,
                         standings=standings)

@tournament_bp.route('/<int:tournament_id>/pairings')
def view_pairings(tournament_id):
    if not session.get('name'):
        return redirect(url_for('auth.login'))
    
    # Get tournament details
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
    tournament = cursor.fetchone()
    
    if not tournament:
        flash('Tournament not found', 'error')
        return redirect(url_for('tournament.index'))
    
    # Get all rounds and their pairings
    cursor.execute('''
    SELECT r.id as round_id, r.round_number, r.status,
           p.id as pairing_id, p.white_player_id, p.black_player_id, p.result, p.board_number,
           wp.name as white_name, bp.name as black_name
    FROM rounds r
    LEFT JOIN pairings p ON r.id = p.round_id
    LEFT JOIN players wp ON p.white_player_id = wp.id
    LEFT JOIN players bp ON p.black_player_id = bp.id
    WHERE r.tournament_id = ?
    ORDER BY r.round_number, p.board_number
    ''', (tournament_id,))
    
    rounds = {}
    for row in cursor.fetchall():
        round_id = row[0]
        if round_id not in rounds:
            rounds[round_id] = {
                'round_number': row[1],
                'status': row[2],
                'pairings': []
            }
        
        if row[3]:  # pairing_id
            rounds[round_id]['pairings'].append({
                'id': row[3],
                'white_player_id': row[4],
                'black_player_id': row[5],
                'result': row[6],
                'board_number': row[7],
                'white_name': row[8],
                'black_name': row[9] if row[9] else 'BYE'
            })
    
    return render_template('tournament/pairings.html',
                         tournament=tournament,
                         rounds=rounds)
