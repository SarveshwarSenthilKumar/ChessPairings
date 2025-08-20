from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort, current_app
from sql import SQL
from datetime import datetime, timedelta
import pytz
import math
import random
import os
from functools import wraps

# Initialize Blueprint
tournament_bp = Blueprint('tournament', __name__)

def get_db():
    """Get a database connection."""
    if not os.path.exists('tournament.db'):
        current_app.init_db()
    return SQL("sqlite:///tournament.db")

def handle_db_errors(f):
    """Decorator to handle database errors."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"Database error: {str(e)}")
            flash('A database error occurred. Please try again later.', 'danger')
            return redirect(url_for('index'))
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'name' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_tournament(tournament_id):
    """Helper function to get a tournament by ID and check permissions"""
    db = get_db()
    try:
        tournament = db.execute("""
            SELECT t.*, 
                   (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count
            FROM tournaments t
            WHERE t.id = ?
        """, tournament_id)
        
        if not tournament:
            abort(404, "Tournament not found")
        
        tournament = tournament[0]
        
        # Check if user has access to this tournament
        if tournament['created_by'] != session.get('name'):
            # Check if user has a role in this tournament
            role = db.execute("""
                SELECT role FROM user_tournament_roles 
                WHERE username = ? AND tournament_id = ?
            """, session.get('name'), tournament_id)
            
            if not role:
                abort(403, "You don't have permission to access this tournament")
        
        return tournament
    except Exception as e:
        current_app.logger.error(f"Error getting tournament: {str(e)}")
        abort(500, "Error retrieving tournament information")

@tournament_bp.route('/tournaments')
@login_required
@handle_db_errors
def list_tournaments():
    """List all tournaments the user has access to."""
    db = get_db()
    try:
        tournaments = db.execute("""
            SELECT t.*, 
                   (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count
            FROM tournaments t
            LEFT JOIN user_tournament_roles r ON t.id = r.tournament_id
            WHERE t.created_by = ? OR r.username = ?
            ORDER BY t.start_date DESC, t.name
        """, session.get('name'), session.get('name'))
        
        return render_template('tournaments/list.html', tournaments=tournaments)
    except Exception as e:
        current_app.logger.error(f"Error listing tournaments: {str(e)}")
        flash('An error occurred while retrieving tournaments.', 'danger')
        return redirect(url_for('index'))

@tournament_bp.route('/tournaments/create', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def create_tournament():
    """Create a new tournament."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        location = request.form.get('location')
        time_control = request.form.get('time_control')
        rounds = int(request.form.get('rounds', 5))
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not name or not start_date or not end_date:
            flash('Please fill in all required fields.', 'danger')
            return render_template('tournaments/create.html')
        
        # Convert dates to proper format
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return render_template('tournaments/create.html')
        
        # Insert new tournament
        tournament_id = db.execute("""
            INSERT INTO tournaments 
            (name, description, location, time_control, rounds, start_date, end_date, created_by, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'upcoming')
        """, name, description, location, time_control, rounds, start_date, end_date, session['name'])
        
        # Add creator as tournament admin
        db.execute("""
            INSERT INTO user_tournament_roles (username, tournament_id, role)
            VALUES (?, ?, 'admin')
        """, session['name'], tournament_id)
        
        flash('Tournament created successfully!', 'success')
        return redirect(url_for('tournament.view_tournament', tournament_id=tournament_id))
    
    # Set default dates (today and one week from today)
    today = datetime.now().strftime('%Y-%m-%d')
    one_week_later = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    return render_template('tournaments/create.html', default_start_date=today, default_end_date=one_week_later)

@tournament_bp.route('/tournaments/<int:tournament_id>')
@login_required
def view_tournament(tournament_id):
    # Get tournament details
    tournament = get_tournament(tournament_id)
    
    # Get tournament players with their current scores
    players = db.execute("""
        SELECT p.*, tp.current_score, tp.tiebreak1, tp.tiebreak2, tp.tiebreak3
        FROM players p
        JOIN tournament_players tp ON p.id = tp.player_id
        WHERE tp.tournament_id = ?
        ORDER BY tp.current_score DESC, tp.tiebreak1 DESC, tp.tiebreak2 DESC, tp.tiebreak3 DESC, p.rating DESC
    """, tournament_id)
    
    # Get rounds and matches
    rounds = db.execute("""
        SELECT r.*, 
               (SELECT COUNT(*) FROM matches m 
                WHERE m.round_id = r.id AND m.status = 'completed') as completed_matches,
               (SELECT COUNT(*) FROM matches m WHERE m.round_id = r.id) as total_matches
        FROM rounds r
        WHERE r.tournament_id = ?
        ORDER BY r.round_number
    """, tournament_id)
    
    # Calculate tournament progress
    if tournament['status'] == 'completed':
        progress = 100
    elif tournament['status'] == 'upcoming':
        progress = 0
    else:
        total_rounds = tournament['rounds']
        current_round = tournament['current_round'] or 0
        if total_rounds > 0:
            progress = min(100, int((current_round / total_rounds) * 100))
        else:
            progress = 0
    
    return render_template('tournaments/view.html', 
                         tournament=tournament, 
                         players=players, 
                         rounds=rounds,
                         progress=progress)

@tournament_bp.route('/tournaments/<int:tournament_id>/update', methods=['POST'])
@login_required
def update_tournament(tournament_id):
    tournament = get_tournament(tournament_id)
    
    # Only allow updates if user is the creator or has admin role
    if tournament['created_by'] != session['name']:
        role = db.execute("""
            SELECT role FROM user_tournament_roles 
            WHERE username = ? AND tournament_id = ? AND role = 'admin'
        """, session['name'], tournament_id)
        
        if not role:
            flash('You do not have permission to update this tournament.', 'danger')
            return redirect(url_for('tournament.view_tournament', tournament_id=tournament_id))
    
    # Handle form data
    name = request.form.get('name')
    description = request.form.get('description')
    location = request.form.get('location')
    time_control = request.form.get('time_control')
    rounds = request.form.get('rounds')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    status = request.form.get('status')
    
    # Update fields that were provided
    update_fields = []
    params = []
    
    if name is not None:
        update_fields.append("name = ?")
        params.append(name)
    
    if description is not None:
        update_fields.append("description = ?")
        params.append(description)
    
    if location is not None:
        update_fields.append("location = ?")
        params.append(location)
    
    if time_control is not None:
        update_fields.append("time_control = ?")
        params.append(time_control)
    
    if rounds is not None:
        update_fields.append("rounds = ?")
        params.append(int(rounds))
    
    if start_date is not None:
        update_fields.append("start_date = ?")
        params.append(start_date)
    
    if end_date is not None:
        update_fields.append("end_date = ?")
        params.append(end_date)
    
    if status is not None and status in ['upcoming', 'ongoing', 'completed']:
        update_fields.append("status = ?")
        params.append(status)
    
    # Add updated_at timestamp
    update_fields.append("updated_at = ?")
    params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # Only proceed if there are fields to update
    if update_fields:
        query = "UPDATE tournaments SET " + ", ".join(update_fields) + " WHERE id = ?"
        params.append(tournament_id)
        db.execute(query, *params)
        
        flash('Tournament updated successfully!', 'success')
    
    return redirect(url_for('tournament.view_tournament', tournament_id=tournament_id))
