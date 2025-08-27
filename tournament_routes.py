from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify
from flask_wtf.csrf import generate_csrf
from flask_wtf import FlaskForm
from wtforms import SelectField, BooleanField, IntegerField, StringField
from wtforms.validators import DataRequired, NumberRange
import os
import pandas as pd
from werkzeug.utils import secure_filename
from functools import wraps
from types import SimpleNamespace
from tournament_db import TournamentDB
import os
import sqlite3
from datetime import datetime

# Create blueprint
tournament_bp = Blueprint('tournament', __name__, template_folder='templates')

# Database connection
def get_db():
    if 'db' not in g:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tournament.db')
        g.db = TournamentDB(db_path)
    return g.db

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Tournament routes
@tournament_bp.route('/')
@login_required
def index():
    """Show tournaments created by the current user."""
    try:
        db = get_db()
        user_id = session.get('user_id')
        tournaments = db.get_tournaments_by_creator(user_id) if user_id else []
        return render_template('tournament/index.html', tournaments=tournaments)
    except Exception as e:
        print(f"Error retrieving tournaments: {e}")
        flash('An error occurred while retrieving your tournaments.', 'error')
        return render_template('tournament/index.html', tournaments=[])

@tournament_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new tournament."""
    db = get_db()
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            rounds = request.form.get('rounds', 5, type=int)
            time_control = request.form.get('time_control')
            location = request.form.get('location')
            description = request.form.get('description')
            
            # Basic validation
            if not all([name, start_date, end_date]):
                flash('Please fill in all required fields', 'error')
                return render_template('tournament/create.html')
                
            # Create the tournament
            tournament_id = db.create_tournament(
                name=name,
                location=location,
                start_date=start_date,
                end_date=end_date,
                rounds=rounds,
                time_control=time_control,
                creator_id=session.get('user_id'),
                description=description
            )
            
            if tournament_id:
                flash('Tournament created successfully!', 'success')
                return redirect(url_for('tournament.view', tournament_id=tournament_id))
            else:
                flash('Failed to create tournament. Please try again.', 'error')
                
        except Exception as e:
            print(f"Error creating tournament: {e}")
            flash('An error occurred while creating the tournament. Please try again.', 'error')
    
    # For GET request or if there was an error
    return render_template('tournament/create.html')

@tournament_bp.route('/<int:tournament_id>')
@login_required
def view(tournament_id):
    """View tournament details."""
    try:
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        
        # Check if tournament exists
        if not tournament:
            flash('Tournament not found.', 'danger')
            return redirect(url_for('tournament.index'))
            
        # Ensure tournament is a dictionary
        if not isinstance(tournament, dict):
            tournament = dict(tournament)
            
        # Check if user is the creator of the tournament
        creator_id = tournament.get('creator_id')
        user_id = session.get('user_id')
        
        if creator_id != user_id:
            flash('You do not have permission to view this tournament.', 'danger')
            return redirect(url_for('tournament.index'))
            
        # Ensure prize_winners exists in tournament
        if 'prize_winners' not in tournament:
            tournament['prize_winners'] = 0
            
        # Get current round and its pairings
        current_round = db.get_current_round(tournament_id)
        pairings = []
        if current_round:
            pairings = db.get_round_pairings(current_round['id'])
            
        # Get view type (individual or team)
        view_type = request.args.get('view', 'individual')
        
        # Get standings based on view type
        standings = db.get_standings(tournament_id, view_type=view_type)
        
        return render_template('tournament/view.html', 
                            tournament=tournament,
                            current_round=current_round,
                            pairings=pairings,
                            standings=standings,
                            view_type=view_type)
    except Exception as e:
        print(f"Error viewing tournament {tournament_id}: {e}")
        flash('An error occurred while loading the tournament.', 'error')
        return redirect(url_for('tournament.index'))

@tournament_bp.route('/<int:tournament_id>/players/<int:player_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_player(tournament_id, player_id):
    """Edit a player's details."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    player = db.get_player(player_id)
    if not player:
        flash('Player not found.', 'danger')
        return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        rating = request.form.get('rating', 0, type=int)
        
        if not name:
            flash('Name is required.', 'danger')
        elif rating < 0:
            flash('Rating must be a positive number.', 'danger')
        else:
            if db.update_player(player_id, name, rating):
                flash('Player updated successfully!', 'success')
                return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))
            else:
                flash('Failed to update player. Please try again.', 'error')
    
    return render_template('tournament/edit_player.html', 
                         tournament=tournament, 
                         player=player)

@tournament_bp.route('/<int:tournament_id>/players', methods=['GET', 'POST'])
@login_required
def manage_players(tournament_id):
    """Manage tournament players."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    if request.method == 'POST':
        if 'name' in request.form:  # Creating a new player
            name = request.form.get('name', '').strip()
            rating = request.form.get('rating', 1200, type=int)
            team = request.form.get('team', '').strip() or None  # Optional team field
            
            if not name:
                flash('Player name is required.', 'error')
            else:
                try:
                    # Create the new player with current timestamp and optional team
                    db.cursor.execute(
                        "INSERT INTO players (name, rating, team, created_at) VALUES (?, ?, ?, datetime('now'))",
                        (name, rating, team)
                    )
                    player_id = db.cursor.lastrowid
                    
                    # Add the new player to the tournament
                    if db.add_player_to_tournament(tournament_id, player_id):
                        flash(f'Player {name} created and added to tournament!', 'success')
                    else:
                        flash(f'Player {name} was created but could not be added to the tournament.', 'warning')
                    
                    db.conn.commit()
                except sqlite3.Error as e:
                    db.conn.rollback()
                    print(f"Error creating player: {e}")
                    flash('An error occurred while creating the player.', 'error')
                    
        elif 'player_id' in request.form:  # Adding an existing player
            player_id = request.form.get('player_id')
            if player_id:
                if db.add_player_to_tournament(tournament_id, int(player_id)):
                    flash('Player added to tournament!', 'success')
                else:
                    flash('Player is already in the tournament.', 'warning')
                    
        elif 'remove_player_id' in request.form:  # Removing a player
            player_id = request.form.get('remove_player_id')
            if player_id:
                if db.remove_player_from_tournament(tournament_id, int(player_id)):
                    flash('Player removed from tournament!', 'success')
                else:
                    flash('Failed to remove player from tournament.', 'error')
    
    # Get all players and tournament players
    all_players = db.get_all_players()
    tournament_players = db.get_tournament_players(tournament_id)
    
    # Get player IDs already in the tournament for filtering
    tournament_player_ids = {p['id'] for p in tournament_players}
    available_players = [p for p in all_players if p['id'] not in tournament_player_ids]
    
    return render_template('tournament/manage_players.html',
                         tournament=tournament,
                         tournament_players=tournament_players,
                         available_players=available_players)

# Form for generating pairings
class PairingsForm(FlaskForm):
    pairing_method = SelectField('Pairing Method', 
                              choices=[
                                  ('swiss', 'Swiss System (Default)'),
                                  ('round_robin', 'Round Robin'),
                                  ('manual', 'Manual Pairing')
                              ],
                              default='swiss')
    check_color_balance = BooleanField('Try to balance colors', default=True)
    avoid_same_pairings = BooleanField('Avoid previous pairings', default=True)

# Form for assigning byes
class ByeForm(FlaskForm):
    player_id = SelectField('Player', coerce=int, validators=[DataRequired()])
    round_number = SelectField('Round', coerce=int, validators=[DataRequired()])

@tournament_bp.route('/<int:tournament_id>/byes', methods=['GET'])
@login_required
def manage_byes(tournament_id):
    """Manage byes for a tournament."""
    try:
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'error')
            return redirect(url_for('tournament.index'))
            
        # Get all players in the tournament
        players = db.get_tournament_players(tournament_id)
        
        # Get all assigned byes
        byes = db.get_manual_byes(tournament_id)
        
        # Prepare form
        form = ByeForm()
        
        # Populate player choices
        form.player_id.choices = [(p['id'], f"{p['name']} ({p.get('rating', 'Unrated')})") 
                                for p in players]
        
        # Populate round choices (future rounds only)
        current_round = db.get_current_round(tournament_id)
        current_round_num = current_round['round_number'] if current_round else 1
        form.round_number.choices = [(i, f"Round {i}") 
                                   for i in range(current_round_num, tournament['rounds'] + 1)]
        
        return render_template('tournament/manage_byes.html',
                             tournament=tournament,
                             players=players,
                             byes=byes,
                             form=form)
    except Exception as e:
        print(f"Error managing byes: {e}")
        flash('An error occurred while loading the bye management page.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/byes/assign', methods=['POST'])
@login_required
def assign_bye(tournament_id):
    """Assign a bye to a player for a specific round."""
    if not session.get('user_id'):
        flash('You must be logged in to assign byes.', 'error')
        return redirect(url_for('auth.login', next=request.url))
        
    db = get_db()
    try:
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'error')
            return redirect(url_for('tournament.index'))
            
        player_id = request.form.get('player_id', type=int)
        round_number = request.form.get('round_number', type=int)
        
        if not player_id or not round_number:
            flash('Please select both a player and a round.', 'error')
            return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
        
        # Check if the round has already been completed
        current_round = db.get_current_round(tournament_id)
        if current_round and round_number < current_round['round_number']:
            flash('Cannot assign a bye to a completed round.', 'error')
            return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
            
        # Check if the player is already assigned a bye for this round
        existing_bye = db.get_manual_bye(tournament_id, player_id, round_number)
        if existing_bye:
            flash('This player already has a bye assigned for the selected round.', 'warning')
            return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
            
        # Assign the bye
        if db.assign_manual_bye(tournament_id, player_id, round_number, session['user_id']):
            flash('Bye assigned successfully!', 'success')
        else:
            flash('Failed to assign bye. Please try again.', 'error')
        
    except Exception as e:
        print(f"Error assigning bye: {e}")
        flash(f'An error occurred while assigning the bye: {str(e)}', 'error')
    
    return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/byes/<int:bye_id>/remove', methods=['POST'])
@login_required
def remove_bye(tournament_id, bye_id):
    """Remove an assigned bye."""
    if not session.get('user_id'):
        flash('You must be logged in to remove byes.', 'error')
        return redirect(url_for('auth.login'))
        
    db = get_db()
    try:
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'error')
            return redirect(url_for('tournament.index'))
            
        # Get the bye details before removing
        db.cursor.execute("""
            SELECT id, player_id, round_number 
            FROM manual_byes 
            WHERE id = ? AND tournament_id = ?
        """, (bye_id, tournament_id))
        
        bye = db.cursor.fetchone()
        if not bye:
            flash('Bye assignment not found.', 'error')
            return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
        
        # Check if the round has already started
        current_round = db.get_current_round(tournament_id)
        if current_round and bye['round_number'] <= current_round['round_number']:
            flash('Cannot remove byes from rounds that have already started.', 'error')
            return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
        
        # Remove the bye
        if db.remove_manual_bye(bye_id):
            flash('Bye removed successfully!', 'success')
        else:
            flash('Failed to remove bye. Please try again.', 'error')
        
    except Exception as e:
        print(f"Error removing bye: {e}")
        flash(f'An error occurred while removing the bye: {str(e)}', 'error')
    
    return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/pairings', methods=['GET', 'POST'])
@login_required
def manage_pairings(tournament_id):
    """Manage tournament pairings."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    # Ensure tournament is a dictionary
    if isinstance(tournament, dict):
        tournament = SimpleNamespace(**tournament)
    
    current_round = db.get_current_round(tournament_id)
    form = PairingsForm()
    
    # Load pairings for the current round if it exists
    pairings = []
    if current_round:
        pairings = db.get_pairings(current_round.get('id'))
    
    # Handle form submission for completing the current round
    if request.method == 'POST' and 'complete_round' in request.form:
        if not current_round:
            flash('No active round to complete.', 'warning')
            return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
            
        # Verify all results are in
        all_results_in = all(p.get('result') for p in pairings if p.get('black_player_id') is not None)
        if not all_results_in:
            flash('Cannot complete round: not all results have been recorded.', 'warning')
            return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
            
        # Mark current round as completed
        db.complete_round(current_round['id'])
        current_round_num = current_round['round_number']
        
        # If this was the last round, redirect to standings
        if current_round_num >= tournament.rounds:
            flash('Tournament completed successfully!', 'success')
            return redirect(url_for('tournament.standings', tournament_id=tournament_id))
            
        # Create next round
        next_round_num = current_round_num + 1
        db.start_round(tournament_id, next_round_num)
        next_round = db.get_current_round(tournament_id)
        
        # Process any bye requests for the new round
        players_needing_byes = db.get_players_with_bye_requests(tournament_id, next_round_num)
        for player in players_needing_byes:
            db.create_pairing(next_round['id'], player['player_id'], None, 0)  # Board 0 for byes
            flash(f'Assigned bye to {player["name"]} for round {next_round_num}', 'info')
        
        # Generate pairings for the remaining players
        method = 'swiss'  # Default to Swiss system
        success = db.generate_pairings(tournament_id, next_round['id'], method=method)
        
        if success:
            flash(f'Round {next_round_num} has been created and pairings generated!', 'success')
        else:
            flash('Failed to generate pairings for the next round.', 'danger')
            
        return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
        
    # Handle form submission for generating pairings (initial generation)
    elif form.validate_on_submit():
        if not current_round:
            # If no current round, create the first round
            round_num = 1
            db.start_round(tournament_id, round_num)
            current_round = db.get_current_round(tournament_id)
            if not current_round:
                flash('Failed to create a new round.', 'danger')
                return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
        
        # Generate pairings using the selected method
        method = form.pairing_method.data
        success = db.generate_pairings(
            tournament_id,
            current_round['id'],
            method=method
        )
        
        if success:
            flash(f'Pairings generated successfully using {method} method!', 'success')
        else:
            flash('Failed to generate pairings. Please try again.', 'danger')
        
        return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
    
    # Ensure pairings are loaded for the current round
    pairings = []
    if current_round:
        pairings = db.get_pairings(current_round.get('id'))
        
    # Handle round completion and next round generation
    elif (request.args.get('generate_next') == 'True' or request.args.get('complete_round') == 'True') and current_round:
        # If completing the current round, verify all results are in
        if request.args.get('complete_round') == 'True':
            all_results_in = all(p.get('result') for p in pairings if p.get('black_player_id') is not None)
            if not all_results_in:
                flash('Cannot complete round: not all results have been recorded.', 'warning')
                return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
            
            # Mark current round as completed
            db.complete_round(current_round['id'])
            flash(f'Round {current_round["round_number"]} has been completed successfully!', 'success')
            
            # If this was the last round, redirect to standings
            if current_round['round_number'] >= tournament.rounds:
                flash('Tournament has been completed!', 'success')
                return redirect(url_for('tournament.standings', tournament_id=tournament_id))
            
            # If not the last round, proceed to generate next round
            next_round_num = current_round['round_number'] + 1
        else:
            # For direct next round generation (backward compatibility)
            next_round_num = current_round['round_number'] + 1
        
        # Create new round if we haven't reached the maximum
        if next_round_num > tournament.rounds:
            flash('Tournament has reached the maximum number of rounds.', 'warning')
            return redirect(url_for('tournament.standings', tournament_id=tournament_id))
            
        # Create new round
        db.start_round(tournament_id, next_round_num)
        current_round = db.get_current_round(tournament_id)
        
        # Process any bye requests for this round
        players_needing_byes = db.get_players_with_bye_requests(tournament_id, next_round_num)
        for player in players_needing_byes:
            db.create_pairing(current_round['id'], player['player_id'], None, 0)  # Board 0 for byes
            flash(f'Assigned bye to {player["name"]} for round {next_round_num}', 'info')
        
        # Generate pairings for the remaining players using the selected method
        method = 'swiss'  # Default to Swiss system
        if hasattr(request, 'form') and request.form.get('pairing_method'):
            method = request.form.get('pairing_method')
            
        success = db.generate_pairings(
            tournament_id,
            current_round['id'],
            method=method
        )
        
        if success:
            flash(f'Round {next_round_num} has been created and pairings generated!', 'success')
        else:
            flash('Failed to generate pairings for the next round.', 'danger')
            
        return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
    
    # Ensure current_round is properly formatted for the template
    pairings = []
    current_round_obj = None
    
    if current_round:
        pairings = db.get_pairings(current_round.get('id'))
        # Ensure all required fields are present
        current_round.setdefault('round_number', 0)
        # Create a copy of the dictionary to avoid modifying the original
        round_data = dict(current_round)
        # Ensure is_completed is set
        round_data['is_completed'] = bool(round_data.get('is_completed', 0))
        # Convert to SimpleNamespace for dot notation in template
        current_round_obj = SimpleNamespace(**round_data)
    
    return render_template(
        'tournament/pairings.html',
        tournament=tournament,
        current_round=current_round_obj,
        pairings=pairings,
        form=form
    )

@tournament_bp.route('/<int:tournament_id>/pairing/<int:pairing_id>/result', methods=['POST'])
@login_required
def submit_result(tournament_id, pairing_id):
    """Submit a game result."""
    print(f"Received request to submit result for tournament {tournament_id}, pairing {pairing_id}")
    print(f"Form data: {request.form}")
    
    try:
        db = get_db()
        
        # Get form data
        result = request.form.get('result')
        csrf_token = request.form.get('csrf_token')
        
        # Verify CSRF token using Flask-WTF's built-in validation
        try:
            from flask_wtf.csrf import validate_csrf
            validate_csrf(csrf_token)
        except Exception as e:
            print(f"CSRF validation error: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Invalid or expired security token. Please refresh the page and try again.',
                'error': 'invalid_csrf_token'
            }), 403
        
        # Check if the tournament exists and user has access
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            return jsonify({
                'success': False,
                'message': 'Tournament not found.'
            }), 404
            
        # Check if the current user is the tournament creator or admin
        if tournament['creator_id'] != session.get('user_id') and not session.get('is_admin', False):
            return jsonify({
                'success': False,
                'message': 'You are not authorized to record results for this tournament.'
            }), 403
        
        # Check if the pairing exists and belongs to this tournament
        pairing = db.cursor.execute(
            """
            SELECT p.* 
            FROM pairings p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.id = ? AND r.tournament_id = ?
            """, (pairing_id, tournament_id)
        ).fetchone()
        
        if not pairing:
            return jsonify({
                'success': False,
                'message': 'Pairing not found in this tournament.'
            }), 404
        
        # Record the result
        result_to_save = result if result != '*' else None
        print(f"Attempting to record result: {result_to_save}")
        
        try:
            success = db.record_result(pairing_id, result_to_save)
            if not success:
                return jsonify({
                    'success': False,
                    'message': 'Failed to record the result. Please try again.',
                    'error': 'record_failed'
                }), 500
                
            # Generate a new CSRF token for the next request
            new_csrf_token = generate_csrf()
            session['csrf_token'] = new_csrf_token
            
            # Make sure the session is saved
            session.modified = True
            
            return jsonify({
                'success': True,
                'message': 'Result recorded successfully!',
                'new_csrf_token': new_csrf_token
            })
            
        except Exception as e:
            error_msg = f"Error in record_result: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': 'An error occurred while recording the result.',
                'error': 'server_error',
                'details': str(e)
            }), 500
            
    except sqlite3.Error as e:
        error_msg = f"Database error recording result: {str(e)}"
        print(error_msg)
        return jsonify({
            'success': False,
            'message': 'A database error occurred while recording the result.',
            'error': str(e)
        }), 500
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e) or 'An error occurred while recording the result.',
            'error': str(e)
        }), 500

@tournament_bp.route('/<int:tournament_id>/standings')
@login_required
def standings(tournament_id):
    """View tournament standings."""
    try:
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'danger')
            return redirect(url_for('tournament.index'))
        
        # Get view type (individual or team)
        view_type = request.args.get('view', 'individual')
        
        # Ensure tournament is a dictionary and has prize_winners key with default value 0 if not set
        if isinstance(tournament, dict):
            tournament = SimpleNamespace(**tournament)
            
        current_round = db.get_current_round(tournament_id)
        standings_data = []
        if hasattr(db, 'get_standings'):
            standings_data = db.get_standings(tournament_id, view_type=view_type) or []
            
        # Check if current round is complete and if there are more rounds to play
        is_round_complete = db.is_current_round_complete(tournament_id) if current_round else False
        has_next_round = current_round and current_round['round_number'] < tournament.rounds if current_round else False
        
        return render_template(
            'tournament/standings.html',
            tournament=tournament,
            standings=standings_data,
            current_round=current_round,
            prize_winners=tournament.prize_winners,
            is_round_complete=is_round_complete,
            has_next_round=has_next_round,
            view_type=view_type
        )
    except Exception as e:
        print(f"Error in standings route: {e}")
        flash('An error occurred while loading the standings.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/rounds')
@login_required
def rounds(tournament_id):
    """View all rounds in the tournament."""
    try:
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'danger')
            return redirect(url_for('tournament.index'))
        
        # Safely get rounds if the method exists
        rounds_data = []
        if hasattr(db, 'get_tournament_rounds'):
            rounds_data = db.get_tournament_rounds(tournament_id) or []
        
        # Provide empty prize_winners list if used in the template
        return render_template(
            'tournament/rounds.html',
            tournament=tournament,
            rounds=rounds_data,
            prize_winners=[]  # Add empty prize_winners list
        )
    except Exception as e:
        print(f"Error in rounds route: {e}")
        flash('An error occurred while loading the rounds.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/round/<int:round_id>')
@login_required
def view_round(round_id):
    """View a specific round's pairings."""
    db = get_db()
    round_data = db.get_round(round_id)
    if not round_data:
        flash('Round not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    tournament = db.get_tournament(round_data['tournament_id'])
    pairings = db.get_pairings(round_id)
    
    return render_template(
        'tournament/round.html',
        tournament=tournament,
        round_data=round_data,
        pairings=pairings
    )

@tournament_bp.route('/<int:tournament_id>/conclude', methods=['POST'])
@login_required
def conclude_tournament(tournament_id):
    """Conclude a tournament."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    
    # Check if tournament exists and user is the creator
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
        
    if tournament['creator_id'] != session.get('user_id'):
        flash('You do not have permission to conclude this tournament.', 'danger')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    # Update tournament status to completed
    if db.update_tournament_status(tournament_id, 'completed'):
        flash('Tournament has been concluded successfully!', 'success')
    else:
        flash('Failed to conclude tournament. Please try again.', 'danger')
    
    return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/delete', methods=['POST'])
@login_required
def delete_tournament(tournament_id):
    """Delete a tournament and all its data."""
    db = get_db()
    user_id = session.get('user_id')
    
    if not user_id:
        flash('You must be logged in to delete a tournament.', 'error')
        return redirect(url_for('auth.login'))
    
    # Get the tournament to verify it exists and get creator_id
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'error')
        return redirect(url_for('tournament.index'))
    
    # Only allow the creator to delete
    if tournament['creator_id'] != user_id:
        flash('You do not have permission to delete this tournament.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    # Delete the tournament
    if db.delete_tournament(tournament_id, user_id):
        flash('Tournament deleted successfully.', 'success')
        return redirect(url_for('tournament.index'))
    else:
        flash('Failed to delete tournament. Please try again.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

# Teardown function to close database connection
@tournament_bp.teardown_app_request
def teardown_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@tournament_bp.teardown_request
def teardown_request(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}

@tournament_bp.route('/<int:tournament_id>/export')
@login_required
def export_players(tournament_id):
    """Export players to a CSV or Excel file."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    # Get players with their team information
    players = db.get_players(tournament_id)
    
    # Convert to DataFrame
    import pandas as pd
    from io import BytesIO
    
    # Create a DataFrame with the required columns
    data = []
    for player in players:
        data.append({
            'Name': player['name'],
            'Team': player.get('team', ''),
            'Rating': player['rating'],
            'Federation': player.get('federation', '')
        })
    
    df = pd.DataFrame(data)
    
    # Create output
    output = BytesIO()
    
    # Get the requested format (default to CSV)
    export_format = request.args.get('format', 'csv').lower()
    
    if export_format == 'xlsx':
        # Export to Excel
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Players')
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        extension = 'xlsx'
    else:
        # Default to CSV
        output = BytesIO()
        df.to_csv(output, index=False)
        mimetype = 'text/csv'
        extension = 'csv'
    
    output.seek(0)
    
    # Create a response with the file
    from flask import send_file
    return send_file(
        output,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{tournament['name'].replace(' ', '_')}_players.{extension}"
    )

@tournament_bp.route('/<int:tournament_id>/import', methods=['POST'])
@login_required
def import_players(tournament_id):
    """Import players from a spreadsheet file."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))

    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))
    
    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload an Excel (.xlsx, .xls) or CSV file.', 'error')
        return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))

    try:
        # Read the file into a pandas DataFrame
        if file.filename.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:  # CSV
            df = pd.read_csv(file)
        
        # Convert column names to lowercase for case-insensitive matching
        df.columns = [col.lower() for col in df.columns]
        
        # Check if required columns exist
        if 'name' not in df.columns:
            flash('Spreadsheet must contain a "name" column', 'error')
            return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))
        
        # Process each row
        success_count = 0
        error_messages = []
        
        for _, row in df.iterrows():
            try:
                name = str(row['name']).strip()
                if not name:
                    error_messages.append(f'Skipped: Empty name in row {_ + 2}')
                    continue
                    
                rating = int(row.get('rating', 1200))
                team = str(row.get('team', '')).strip() or None
                
                # Create the new player with current timestamp and team
                db.cursor.execute(
                    "INSERT INTO players (name, rating, team, created_at) VALUES (?, ?, ?, datetime('now'))",
                    (name, rating, team)
                )
                player_id = db.cursor.lastrowid
                
                # Add to tournament
                if db.add_player_to_tournament(tournament_id, player_id):
                    success_count += 1
                else:
                    error_messages.append(f'Player "{name}" already in tournament')
                
            except ValueError as e:
                error_messages.append(f'Error in row {_ + 2}: {str(e)}')
            except Exception as e:
                error_messages.append(f'Error processing row {_ + 2}: {str(e)}')
        
        db.conn.commit()
        
        if success_count > 0:
            flash(f'Successfully imported {success_count} players!', 'success')
        if error_messages:
            flash('Some players could not be imported. ' + ' '.join(error_messages[:3]) + 
                 ('...' if len(error_messages) > 3 else ''), 'warning')
            
    except Exception as e:
        db.conn.rollback()
        current_app.logger.error(f'Error importing players: {str(e)}', exc_info=True)
        flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('tournament.manage_players', tournament_id=tournament_id))
