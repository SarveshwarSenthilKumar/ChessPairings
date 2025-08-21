from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, g, jsonify
from tournament_db import TournamentDB
from pairing_algorithm import SwissPairing
from auth import login_required
import os
import sqlite3
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError

# Initialize Blueprint
tournament_bp = Blueprint('tournament', __name__, url_prefix='/tournament')

def get_tournament_db():
    """Get the tournament database connection."""
    if 'tournament_db' not in g:
        db_path = os.path.join(current_app.root_path, 'instance', 'tournament.db')
        g.tournament_db = TournamentDB(db_path)
    return g.tournament_db

@tournament_bp.teardown_request
def teardown_tournament_db(exception=None):
    """Close the tournament database connection at the end of the request."""
    tournament_db = g.pop('tournament_db', None)
    if tournament_db is not None:
        tournament_db.close()

@tournament_bp.route('/')
@login_required
def index():
    """Display all tournaments."""
    try:
        db = get_tournament_db()
        cursor = db.conn.cursor()
        cursor.execute('SELECT * FROM tournaments ORDER BY created_at DESC')
        tournaments = cursor.fetchall()
        
        return render_template('tournament/index.html', tournaments=tournaments)
    except Exception as e:
        current_app.logger.error(f"Error fetching tournaments: {str(e)}")
        flash("An error occurred while fetching tournaments.", "error")
        return render_template('error.html', error="An error occurred while fetching tournaments"), 500

@tournament_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new tournament."""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            rounds = int(request.form.get('rounds', 5))
            
            if not name:
                flash('Tournament name is required', 'error')
                return render_template('tournament/create.html')
            
            # Create tournament
            db = get_tournament_db()
            tournament_id = db.create_tournament(name, rounds)
            
            if tournament_id:
                flash('Tournament created successfully!', 'success')
                return redirect(url_for('tournament.view', tournament_id=tournament_id))
            else:
                flash('Failed to create tournament. Please try again.', 'error')
                return render_template('tournament/create.html')
                
        except ValueError:
            flash('Invalid number of rounds', 'error')
            return render_template('tournament/create.html')
        except Exception as e:
            current_app.logger.error(f"Error creating tournament: {str(e)}")
            flash('An error occurred while creating the tournament.', 'error')
            return render_template('error.html', error="An error occurred while creating the tournament"), 500
    
    return render_template('tournament/create.html')

@tournament_bp.route('/<int:tournament_id>')
@login_required
def view(tournament_id):
    """View tournament details, pairings, and standings."""
    try:
        db = get_tournament_db()
        cursor = db.conn.cursor()
        
        # Get tournament details
        cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
        tournament = cursor.fetchone()
        
        if not tournament:
            flash('Tournament not found', 'error')
            return redirect(url_for('tournament.index'))
        
        # Get players
        cursor.execute('SELECT * FROM players WHERE tournament_id = ?', (tournament_id,))
        players = cursor.fetchall()
        
        # Get current round
        current_round = tournament['current_round']
        
        # Get pairings for current round
        cursor.execute('''
            SELECT p1.name as player1_name, p2.name as player2_name, 
                   pr.id, pr.player1_id, pr.player2_id, pr.result, pr.round_number
            FROM pairings pr
            LEFT JOIN players p1 ON pr.player1_id = p1.id
            LEFT JOIN players p2 ON pr.player2_id = p2.id
            WHERE pr.tournament_id = ? AND pr.round_number = ?
            ORDER BY pr.id
        ''', (tournament_id, current_round))
        pairings = cursor.fetchall()
        
        # Get standings
        cursor.execute('''
            SELECT p.id, p.name, 
                   COALESCE(SUM(CASE 
                       WHEN pr.player1_id = p.id AND pr.result = 1 THEN 1
                       WHEN pr.player2_id = p.id AND pr.result = 2 THEN 1
                       WHEN pr.result = 0.5 THEN 0.5
                       ELSE 0
                   END), 0) as score
            FROM players p
            LEFT JOIN pairings pr ON (pr.player1_id = p.id OR pr.player2_id = p.id) 
                                 AND pr.tournament_id = ? AND pr.result IS NOT NULL
            WHERE p.tournament_id = ?
            GROUP BY p.id, p.name
            ORDER BY score DESC, p.name
        ''', (tournament_id, tournament_id))
        standings = cursor.fetchall()
        
        return render_template('tournament/view.html', 
                             tournament=tournament, 
                             players=players, 
                             pairings=pairings,
                             standings=standings,
                             current_round=current_round)
    except Exception as e:
        current_app.logger.error(f"Error viewing tournament {tournament_id}: {str(e)}")
        flash('An error occurred while loading the tournament.', 'error')
        return render_template('error.html', error="An error occurred while loading the tournament"), 500

@tournament_bp.route('/<int:tournament_id>/add_player', methods=['POST'])
@login_required
def add_player(tournament_id):
    """Add a player to the tournament."""
    try:
        name = request.form.get('name', '').strip()
        rating = int(request.form.get('rating', 0))
        
        if not name:
            flash('Player name is required', 'error')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
        
        db = get_tournament_db()
        success = db.add_player(tournament_id, name, rating)
        
        if success:
            flash('Player added successfully!', 'success')
        else:
            flash('Failed to add player. Please try again.', 'error')
            
    except ValueError:
        flash('Invalid rating value', 'error')
    except Exception as e:
        current_app.logger.error(f"Error adding player to tournament {tournament_id}: {str(e)}")
        flash('An error occurred while adding the player.', 'error')
    
    return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/generate_pairings', methods=['POST'])
@login_required
def generate_pairings(tournament_id):
    """Generate pairings for the next round of the tournament."""
    try:
        db = get_tournament_db()
        cursor = db.conn.cursor()
        
        # Get tournament details
        cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
        tournament = cursor.fetchone()
        
        if not tournament:
            flash('Tournament not found', 'error')
            return redirect(url_for('tournament.index'))
        
        current_round = tournament['current_round']
        
        # Check if all pairings from previous round have results
        if current_round > 0:
            cursor.execute('''
                SELECT COUNT(*) as incomplete
                FROM pairings
                WHERE tournament_id = ? AND round_number = ? AND result IS NULL
            ''', (tournament_id, current_round))
            
            incomplete = cursor.fetchone()['incomplete']
            
            if incomplete > 0:
                flash('Please enter all results for the current round before generating new pairings', 'error')
                return redirect(url_for('tournament.view', tournament_id=tournament_id))
        
        # Initialize pairing system
        pairing_system = SwissPairing(db)
        
        # Generate pairings for next round
        success = pairing_system.create_pairings(tournament_id)
        
        if not success:
            flash('Failed to generate pairings. Not enough players or another error occurred.', 'error')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
        
        # Update tournament round
        cursor.execute('''
            UPDATE tournaments 
            SET current_round = current_round + 1 
            WHERE id = ?
        ''', (tournament_id,))
        
        db.conn.commit()
        flash('Pairings generated successfully!', 'success')
        
    except Exception as e:
        db.conn.rollback()
        current_app.logger.error(f"Error generating pairings for tournament {tournament_id}: {str(e)}")
        flash('An error occurred while generating pairings.', 'error')
    
    return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/standings')
@login_required
def standings(tournament_id):
    """Display tournament standings with tiebreaks."""
    try:
        db = get_tournament_db()
        cursor = db.conn.cursor()
        
        # Get tournament details
        cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
        tournament = cursor.fetchone()
        
        if not tournament:
            flash('Tournament not found', 'error')
            return redirect(url_for('tournament.index'))
        
        # Get standings with tiebreaks
        cursor.execute('''
            WITH results AS (
                SELECT 
                    p.id,
                    p.name,
                    p.rating,
                    SUM(CASE 
                        WHEN (pr.player1_id = p.id AND pr.result = 1) OR 
                             (pr.player2_id = p.id AND pr.result = 2) THEN 1
                        WHEN pr.result = 0.5 THEN 0.5
                        ELSE 0
                    END) as score,
                    GROUP_CONCAT(CASE 
                        WHEN pr.player1_id = p.id THEN pr.player2_id
                        WHEN pr.player2_id = p.id THEN pr.player1_id
                    END, ',') as opponents
                FROM players p
                LEFT JOIN pairings pr ON (pr.player1_id = p.id OR pr.player2_id = p.id)
                WHERE p.tournament_id = ?
                GROUP BY p.id, p.name, p.rating
            )
            SELECT 
                id,
                name,
                rating,
                score,
                (
                    SELECT COALESCE(SUM(r2.score), 0)
                    FROM results r2 
                    WHERE ',' || r1.opponents || ',' LIKE '%,' || r2.id || ',%'
                ) as buchholz
            FROM results r1
            ORDER BY score DESC, buchholz DESC, rating DESC, name
        ''', (tournament_id,))
        
        standings = cursor.fetchall()
        
        return render_template('tournament/standings.html', 
                             tournament=tournament, 
                             standings=standings)
        
    except Exception as e:
        current_app.logger.error(f"Error loading standings for tournament {tournament_id}: {str(e)}")
        flash('An error occurred while loading the standings.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/pairings')
@login_required
def view_pairings(tournament_id):
    """View pairings for all rounds of the tournament."""
    try:
        db = get_tournament_db()
        cursor = db.conn.cursor()
        
        # Get tournament details
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
    
    except Exception as e:
        current_app.logger.error(f"Error loading pairings for tournament {tournament_id}: {str(e)}")
        flash('An error occurred while loading the pairings.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/pairing/<int:pairing_id>/result', methods=['POST'])
@login_required
def record_result(pairing_id):
    """Record the result of a pairing."""
    try:
        # Get the result from the request
        result = request.json.get('result')
        if result not in ['1-0', '0-1', '1/2-1/2']:
            raise BadRequest('Invalid result format. Must be one of: 1-0, 0-1, 1/2-1/2')
        
        db = get_tournament_db()
        cursor = db.conn.cursor()
        
        # Get the pairing details
        cursor.execute('''
            SELECT p.*, r.tournament_id, r.round_number
            FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.id = ?
        ''', (pairing_id,))
        
        pairing = cursor.fetchone()
        if not pairing:
            raise NotFound('Pairing not found')
        
        # Update the pairing with the result
        cursor.execute('''
            UPDATE pairings 
            SET result = ?
            WHERE id = ?
        ''', (result, pairing_id))
        
        db.conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Result recorded successfully',
            'pairing_id': pairing_id,
            'result': result
        })
        
    except BadRequest as e:
        current_app.logger.warning(f"Bad request when recording result: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
        
    except NotFound as e:
        current_app.logger.warning(f"Pairing not found: {pairing_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
        
    except Exception as e:
        db.conn.rollback()
        current_app.logger.error(f"Error recording result for pairing {pairing_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while recording the result.'
        }), 500
