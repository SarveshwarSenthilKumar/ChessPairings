from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify
from flask_wtf.csrf import generate_csrf
from flask_wtf import FlaskForm
from wtforms import SelectField, BooleanField
from wtforms.validators import DataRequired
import os
import pandas as pd
from werkzeug.utils import secure_filename
from functools import wraps
from types import SimpleNamespace
from tournament_db import TournamentDB
import os
import sqlite3

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
            
        return render_template('tournament/view.html', 
                            tournament=tournament,
                            current_round=current_round,
                            pairings=pairings)
    except Exception as e:
        print(f"Error viewing tournament {tournament_id}: {e}")
        flash('An error occurred while loading the tournament.', 'error')
        return redirect(url_for('tournament.index'))

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
            
            if not name:
                flash('Player name is required.', 'error')
            else:
                try:
                    # Create the new player with current timestamp
                    db.cursor.execute(
                        "INSERT INTO players (name, rating, created_at) VALUES (?, ?, datetime('now'))",
                        (name, rating)
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

@tournament_bp.route('/tournament/<int:tournament_id>/pairings', methods=['GET', 'POST'])
@login_required
def manage_pairings(tournament_id):
    """Manage tournament pairings."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    form = PairingsForm()
    current_round = db.get_current_round(tournament_id)
    
    if request.method == 'POST' and form.validate():
        if current_round and current_round.get('status') != 'completed':
            flash('Please complete the current round before generating new pairings.', 'warning')
        else:
            try:
                next_round = (current_round['round_number'] + 1) if current_round else 1
                method = form.pairing_method.data
                
                # Start a new round
                round_id = db.start_round(tournament_id, next_round)
                if not round_id:
                    flash('Failed to create a new round.', 'error')
                    return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
                
                # Generate pairings
                if db.generate_pairings(tournament_id, round_id, method):
                    flash('Pairings generated successfully!', 'success')
                    return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
                else:
                    flash('Error generating pairings. Please try again.', 'error')
            except Exception as e:
                print(f"Error generating pairings: {e}")
                flash('An error occurred while generating pairings.', 'error')
                db.conn.rollback()
    
    # Ensure current_round is properly formatted for the template
    pairings = []
    current_round_obj = None
    
    if current_round:
        pairings = db.get_pairings(current_round.get('id'))
        # Ensure all required fields are present
        current_round.setdefault('round_number', 0)
        # Create a copy of the dictionary to avoid modifying the original
        round_data = dict(current_round)
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
        
        # Ensure tournament has prize_winners attribute with default value 0 if not set
        if not hasattr(tournament, 'prize_winners'):
            tournament.prize_winners = 0
        
        # Safely get current round
        current_round = 0
        if hasattr(db, 'get_current_round'):
            current_round = db.get_current_round(tournament_id) or 0
        
        # Get standings if the method exists
        standings_data = []
        if hasattr(db, 'get_standings'):
            standings_data = db.get_standings(tournament_id) or []
        
        return render_template(
            'tournament/standings.html',
            tournament=tournament,
            standings=standings_data,
            current_round=current_round,
            prize_winners=tournament.prize_winners
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
                
                # Create the new player with current timestamp
                db.cursor.execute(
                    "INSERT INTO players (name, rating, created_at) VALUES (?, ?, datetime('now'))",
                    (name, rating)
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
