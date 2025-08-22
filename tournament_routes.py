from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, g
from datetime import datetime
from functools import wraps
from tournament_db import TournamentDB
import os

# Create blueprint
tournament_bp = Blueprint('tournament', __name__, template_folder='templates')

# Database connection
def get_db():
    if 'db' not in g:
        g.db = TournamentDB('tournament.db')
    return g.db

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Tournament routes
@tournament_bp.route('/')
@login_required
def index():
    """Show all tournaments."""
    db = get_db()
    tournaments = db.get_all_tournaments()
    return render_template('tournament/index.html', tournaments=tournaments)

@tournament_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new tournament."""
    if request.method == 'POST':
        name = request.form.get('name')
        rounds = int(request.form.get('rounds', 5))
        time_control = request.form.get('time_control')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        try:
            db = get_db()
            tournament_id = db.create_tournament(
                name=name,
                rounds=rounds,
                time_control=time_control,
                start_date=start_date,
                end_date=end_date
            )
            flash('Tournament created successfully!', 'success')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
        except Exception as e:
            flash(f'Error creating tournament: {str(e)}', 'danger')
    
    return render_template('tournament/create.html')

@tournament_bp.route('/<int:tournament_id>')
@login_required
def view(tournament_id):
    """View tournament details."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    standings = db.get_standings(tournament_id)
    current_round = db.get_current_round(tournament_id)
    pairings = db.get_pairings(current_round['id']) if current_round else []
    
    return render_template(
        'tournament/view.html',
        tournament=tournament,
        standings=standings,
        current_round=current_round,
        pairings=pairings
    )

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
        player_id = request.form.get('player_id')
        if player_id:
            if db.add_player_to_tournament(tournament_id, player_id):
                flash('Player added to tournament!', 'success')
            else:
                flash('Player is already in the tournament.', 'warning')
    
    players = db.get_all_players()
    tournament_players = db.get_tournament_players(tournament_id)
    
    return render_template(
        'tournament/players.html',
        tournament=tournament,
        players=players,
        tournament_players=tournament_players
    )

@tournament_bp.route('/<int:tournament_id>/pairings', methods=['GET', 'POST'])
@login_required
def manage_pairings(tournament_id):
    """Manage tournament pairings."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    current_round = db.get_current_round(tournament_id)
    
    if request.method == 'POST' and 'generate_pairings' in request.form:
        if current_round and current_round['status'] != 'completed':
            flash('Please complete the current round before generating new pairings.', 'warning')
        else:
            next_round = (current_round['round_number'] + 1) if current_round else 1
            if db.generate_swiss_pairings(tournament_id, next_round):
                flash('Pairings generated successfully!', 'success')
                return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
            else:
                flash('Error generating pairings. Please try again.', 'danger')
    
    pairings = db.get_pairings(current_round['id']) if current_round else []
    
    return render_template(
        'tournament/pairings.html',
        tournament=tournament,
        current_round=current_round,
        pairings=pairings
    )

@tournament_bp.route('/pairing/<int:pairing_id>/result', methods=['POST'])
@login_required
def submit_result(pairing_id):
    """Submit a game result."""
    db = get_db()
    result = request.form.get('result')
    
    if result not in ['1-0', '0-1', '0.5-0.5']:
        flash('Invalid result.', 'danger')
        return redirect(request.referrer)
    
    if db.record_result(pairing_id, result):
        flash('Result recorded successfully!', 'success')
    else:
        flash('Error recording result. Please try again.', 'danger')
    
    return redirect(request.referrer)

@tournament_bp.route('/<int:tournament_id>/standings')
@login_required
def standings(tournament_id):
    """View tournament standings."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    standings_data = db.get_standings(tournament_id)
    
    return render_template(
        'tournament/standings.html',
        tournament=tournament,
        standings=standings_data
    )

@tournament_bp.route('/<int:tournament_id>/rounds')
@login_required
def rounds(tournament_id):
    """View all rounds in the tournament."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    rounds = db.get_tournament_rounds(tournament_id)
    
    return render_template(
        'tournament/rounds.html',
        tournament=tournament,
        rounds=rounds
    )

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
@tournament_bp.teardown_request
def teardown_request(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
