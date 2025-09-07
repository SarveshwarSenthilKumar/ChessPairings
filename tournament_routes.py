from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify, send_file
from flask_wtf.csrf import generate_csrf
from flask_wtf import FlaskForm
from wtforms import SelectField, BooleanField, IntegerField, StringField, TextAreaField, SubmitField, DateField, FloatField
from wtforms.validators import DataRequired, NumberRange, InputRequired
import os
import pandas as pd
import random
from werkzeug.utils import secure_filename
from functools import wraps
from types import SimpleNamespace
from tournament_db import TournamentDB
import os
import sqlite3
from datetime import datetime
from decorators import check_tournament_active
import json
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
from dotenv import load_dotenv
from sql import SQL


# Load environment variables
load_dotenv()

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def regenerate_current_round_pairings(db: TournamentDB, tournament_id: int) -> bool:
    """Regenerate pairings for the current round, preserving any existing results.
    
    Args:
        db: Database connection
        tournament_id: ID of the tournament
        
    Returns:
        bool: True if pairings were regenerated successfully, False otherwise
    """
    try:
        # Get current round
        current_round = db.get_current_round(tournament_id)
        if not current_round:
            return False
            
        round_id = current_round['id']
        
        # Get existing pairings with results
        existing_pairings = db.get_pairings(round_id)
        completed_results = {}
        
        # Store completed results
        for pairing in existing_pairings:
            if pairing.get('result'):
                white_id = pairing.get('white_player_id')
                black_id = pairing.get('black_player_id')
                if white_id and black_id:  # Only store results for actual games, not byes
                    completed_results[(white_id, black_id)] = pairing['result']
        
        # Regenerate pairings
        success = db.generate_pairings(tournament_id, round_id, 'swiss')
        if not success:
            return False
            
        # Get new pairings
        new_pairings = db.get_pairings(round_id)
        
        # Restore completed results where possible
        for pairing in new_pairings:
            white_id = pairing.get('white_player_id')
            black_id = pairing.get('black_player_id')
            
            if not white_id or not black_id:
                continue  # Skip byes
                
            result = completed_results.get((white_id, black_id))
            if result:
                db.update_pairing_result(
                    pairing['id'],
                    white_id,
                    black_id,
                    result,
                    'completed'
                )
                
        return True
        
    except Exception as e:
        print(f"Error regenerating pairings: {e}")
        return False

# Create blueprint
tournament_bp = Blueprint('tournament', __name__, template_folder='templates')

# Database connection
def get_db(f=None):
    if f is None:  # Called as a regular function
        if 'db' not in g:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tournament.db')
            g.db = TournamentDB(db_path)
        return g.db
    
    # Called as a decorator
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'db' not in g:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tournament.db')
            g.db = TournamentDB(db_path)
        return f(*args, **kwargs)
    return decorated_function

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@tournament_bp.route('/<int:tournament_id>/player/<int:player_id>/history')
@login_required
@get_db
def player_history(tournament_id, player_id):
    """Get a player's match history in a tournament."""
    db = g.db
    player = db.get_player(player_id)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    
    # Get tournament for additional context
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    # Get match history with detailed stats
    history = db.get_player_match_history(tournament_id, player_id)
    
    # Prepare response with player info, matches, and stats
    response = {
        'player': {
            'id': player['id'],
            'name': player['name'],
            'rating': player.get('rating')
        },
        'tournament': {
            'id': tournament['id'],
            'name': tournament['name'],
            'status': tournament['status']
        },
        'matches': history['matches'],
        'stats': history['stats']
    }
    
    return jsonify(response)

@tournament_bp.route('/hidden')
@login_required
def hidden_tournaments():
    """View hidden tournaments for the current user."""
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        # Get all tournaments created by the user
        all_tournaments = db.get_tournaments_by_creator(user_id)
        
        # Get hidden tournaments for this user
        hidden_key = f'hidden_tournaments_{user_id}'
        hidden_tournament_ids = set(session.get(hidden_key, []))
        
        # Filter hidden tournaments
        hidden_tournaments = [t for t in all_tournaments if t['id'] in hidden_tournament_ids]
        
        return render_template('tournament/hidden.html', tournaments=hidden_tournaments)
    except Exception as e:
        print(f"Error retrieving hidden tournaments: {e}")
        flash('An error occurred while retrieving hidden tournaments.', 'error')
        return redirect(url_for('tournament.index'))

@tournament_bp.route('/<int:tournament_id>/unhide', methods=['POST'])
@login_required
def unhide_tournament(tournament_id):
    """Unhide a tournament for the current user."""
    try:
        db = get_db()
        user_id = session.get('user_id')
        
        # Remove from hidden tournaments for this user
        hidden_key = f'hidden_tournaments_{user_id}'
        hidden_tournaments = set(session.get(hidden_key, []))
        if tournament_id in hidden_tournaments:
            hidden_tournaments.remove(tournament_id)
            session[hidden_key] = list(hidden_tournaments)
            session.modified = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Tournament was not hidden'}), 400
        
    except Exception as e:
        print(f"Error unhiding tournament: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while unhiding the tournament'}), 500

@tournament_bp.route('/<int:tournament_id>/pin', methods=['POST'])
@login_required
def pin_tournament(tournament_id):
    """Pin a tournament for the current user."""
    try:
        db = get_db()
        user_id = session.get('user_id')
        
        # Add to pinned tournaments for this user
        pinned_key = f'pinned_tournaments_{user_id}'
        pinned_tournaments = set(session.get(pinned_key, []))
        pinned_tournaments.add(tournament_id)
        session[pinned_key] = list(pinned_tournaments)
        session.modified = True
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error pinning tournament: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while pinning the tournament'}), 500

@tournament_bp.route('/<int:tournament_id>/unpin', methods=['POST'])
@login_required
def unpin_tournament(tournament_id):
    """Unpin a tournament for the current user."""
    try:
        db = get_db()
        user_id = session.get('user_id')
        
        # Remove from pinned tournaments for this user
        pinned_key = f'pinned_tournaments_{user_id}'
        pinned_tournaments = set(session.get(pinned_key, []))
        if tournament_id in pinned_tournaments:
            pinned_tournaments.remove(tournament_id)
            session[pinned_key] = list(pinned_tournaments)
            session.modified = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Tournament was not pinned'}), 400
        
    except Exception as e:
        print(f"Error unpinning tournament: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while unpinning the tournament'}), 500

@tournament_bp.route('/<int:tournament_id>/hide', methods=['POST'])
@login_required
def hide_tournament(tournament_id):
    """Hide a tournament from the user's view."""
    try:
        db = get_db()
        user_id = session.get('user_id')
        
        # Add to hidden tournaments for this user
        hidden_key = f'hidden_tournaments_{user_id}'
        hidden_tournaments = set(session.get(hidden_key, []))
        hidden_tournaments.add(tournament_id)
        session[hidden_key] = list(hidden_tournaments)
        
        # Also clean up any share links
        share_link_key = f'share_link_{tournament_id}'
        if share_link_key in session:
            del session[share_link_key]
            
            # Also remove any associated share link data
            share_data_key = f'share_link_data_{tournament_id}'
            if share_data_key in session:
                del session[share_data_key]
        
        session.modified = True
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error hiding tournament: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while hiding the tournament'}), 500

# Tournament routes
@tournament_bp.route('/')
@login_required
def index():
    """Show tournaments created by the current user, excluding hidden ones."""
    db = get_db()
    user_id = session.get('user_id')
    
    try:
        # Get tournaments where user is the creator
        tournaments = db.get_tournaments_by_creator(user_id)
        
        # Get shared tournaments from session
        share_link_tournaments = []
        for key in list(session.keys()):
            if key.startswith('share_link_') and key != f'share_link_{user_id}':
                try:
                    tournament_id = int(key.split('_')[-1])
                    tournament = db.get_tournament(tournament_id)
                    if tournament and not any(t['id'] == tournament_id for t in tournaments):
                        tournament['via_share_link'] = True
                        share_link_tournaments.append(tournament)
                except (ValueError, IndexError):
                    continue
        
        # Combine both lists
        all_tournaments = tournaments + share_link_tournaments
        
        # Get hidden tournaments for this user
        hidden_key = f'hidden_tournaments_{user_id}'
        hidden_tournaments = set(session.get(hidden_key, []))
        
        # Filter out hidden tournaments
        visible_tournaments = [t for t in all_tournaments if t['id'] not in hidden_tournaments]
        
        return render_template('tournament/index.html', tournaments=visible_tournaments)
    except Exception as e:
        print(f"Error retrieving tournaments: {e}")
        import traceback
        traceback.print_exc()
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

@tournament_bp.route('/<int:tournament_id>/settings', methods=['GET', 'POST'])
@login_required
def tournament_settings(tournament_id):
    """Edit tournament settings."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    # Check if user is the creator of the tournament or has a valid share link with edit settings permission
    creator_id = tournament.get('creator_id')
    user_id = session.get('user_id')
    
    # Check for valid share token in the URL with edit settings permission
    token = request.args.get('token')
    has_edit_permission = False
    
    if token:
        is_valid, permissions = validate_share_link(token, tournament_id)
        if is_valid and 'can_edit_settings' in permissions:
            has_edit_permission = True
    
    if creator_id != user_id and not has_edit_permission:
        flash('You do not have permission to edit this tournament.', 'danger')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    form = TournamentSettingsForm()
    
    # Handle form submission
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Get dates from form (already validated)
            start_date = form.start_date.data
            end_date = form.end_date.data
            
            # Update tournament with form data including point settings
            success = db.update_tournament(
                tournament_id=tournament_id,
                name=form.name.data,
                location=form.location.data or None,
                start_date=start_date,
                end_date=end_date,
                rounds=form.rounds.data,
                time_control=form.time_control.data or None,
                description=form.description.data or None,
                comments=form.comments.data or None,
                win_points=form.win_points.data,
                draw_points=form.draw_points.data,
                loss_points=form.loss_points.data,
                bye_points=form.bye_points.data
            )
            
            if success:
                flash('Tournament settings updated successfully!', 'success')
                return redirect(url_for('tournament.view', tournament_id=tournament_id))
            else:
                flash('Failed to update tournament settings. Please try again.', 'danger')
        except Exception as e:
            current_app.logger.error(f"Error updating tournament: {str(e)}")
            flash('An error occurred while updating the tournament. Please try again.', 'danger')
    
    # Pre-populate form for GET request or failed POST
    if request.method == 'GET':
        form.name.data = tournament.get('name')
        form.location.data = tournament.get('location')
        form.comments.data = tournament.get('comments')
        
        # Handle date conversion safely
        if tournament.get('start_date'):
            if isinstance(tournament['start_date'], str):
                form.start_date.data = tournament['start_date'].split()[0]  # Get just the date part
            else:
                form.start_date.data = tournament['start_date'].strftime('%Y-%m-%d')
        
        if tournament.get('end_date'):
            if isinstance(tournament['end_date'], str):
                form.end_date.data = tournament['end_date'].split()[0]  # Get just the date part
            else:
                form.end_date.data = tournament['end_date'].strftime('%Y-%m-%d')
        
        form.rounds.data = tournament.get('rounds', 5)
        form.time_control.data = tournament.get('time_control')
        form.description.data = tournament.get('description')
        
        # Set point settings defaults if not set
        form.win_points.data = tournament.get('win_points', 1.0)
        form.draw_points.data = tournament.get('draw_points', 0.5)
        form.loss_points.data = tournament.get('loss_points', 0.0)
        form.bye_points.data = tournament.get('bye_points', 1.0)
    
    return render_template(
        'tournament/settings.html',
        tournament=tournament,
        form=form
    )

from admin_share_links import validate_share_link
import openai

@tournament_bp.route('/<int:tournament_id>/ai-analysis')
@login_required
@get_db
def ai_analysis(tournament_id):
    """Generate an AI analysis of the tournament."""
    db = g.db
    tournament = db.get_tournament(tournament_id)
    
    if not tournament:
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
    
    try:
        # Get tournament data
        players = db.get_players(tournament_id)
        rounds = db.get_rounds(tournament_id)
        pairings = []
        
        for round_ in rounds:
            round_pairings = db.get_pairings(round_['id'])
            for pairing in round_pairings:
                pairing['round_number'] = round_['round_number']
                pairings.append(pairing)
    
        # Get standings and ensure we have valid data
        standings = db.get_standings(tournament_id) or []
        
        # Check if we have enough data
        if not players or not rounds:
            return jsonify({
                'success': False,
                'error': 'Not enough tournament data available for analysis'
            })
        
        # Prepare player name mapping for lookups
        player_name_map = {p['id']: p['name'] for p in players}
        
        # Prepare standings with safe access to fields
        safe_standings = []
        for i, s in enumerate(standings, 1):
            safe_standings.append({
                'rank': s.get('rank', i),  # Use position in list if rank is missing
                'name': s.get('name', 'Unknown Player'),
                'points': s.get('points', 0),
                'tiebreak1': s.get('tiebreak1', 0),
                'tiebreak2': s.get('tiebreak2', 0)
            })
        
        # Prepare pairings with safe access to fields
        safe_pairings = []
        for p in pairings:
            white_id = p.get('white_player_id')
            black_id = p.get('black_player_id')
            
            safe_pairings.append({
                'round': p.get('round_number', 0),
                'white': player_name_map.get(white_id, 'Unknown') if white_id else 'Bye',
                'black': player_name_map.get(black_id, 'Unknown') if black_id else 'Bye',
                'result': p.get('result', 'Not played')
            })
        
        # Prepare tournament data
        tournament_data = {
            'name': tournament.get('name', 'Unnamed Tournament'),
            'status': tournament.get('status', 'Unknown'),
            'start_date': tournament.get('start_date', 'Unknown'),
            'end_date': tournament.get('end_date', 'Ongoing'),
            'total_players': len(players),
            'total_rounds': len(rounds),
            'players': [{
                'name': p.get('name', 'Unknown Player'),
                'rating': p.get('rating'),
                'team': p.get('team_name')
            } for p in players],
            'standings': safe_standings,
            'pairings': safe_pairings
        }
        
        # Prepare the prompt for the AI
        prompt = f"""Analyze this chess tournament data and provide insights:
        
Tournament: {tournament_data['name']}
Status: {tournament_data['status'].capitalize()}
Players: {tournament_data['total_players']}
Rounds: {tournament_data['total_rounds']}

Top Players:
"""
        # Add top 5 players to the prompt
        for i, player in enumerate(tournament_data['standings'][:5], 1):
            prompt += f"{i}. {player['name']} - {player['points']} points\n"
        
        prompt += "\nRecent Pairings:\n"
        # Add recent pairings to the prompt
        for pairing in tournament_data['pairings'][-10:]:
            prompt += f"Round {pairing['round']}: {pairing['white']} vs {pairing['black']} - {pairing['result']}\n"
        
        prompt += """
        
Provide a brief analysis of the tournament, including:
1. Top performers and their performance
2. Interesting matchups or results
3. Any notable trends or patterns
4. Predictions for the final standings if the tournament is still in progress

Keep the analysis concise and focused on the most interesting aspects.
"""
        
        try:
            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a chess tournament analyst. Provide insightful and concise analysis of the tournament data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content.strip()
        except Exception as api_error:
            print(f"OpenAI API error: {str(api_error)}")
            # Fallback to a simple analysis if API call fails
            top_players = "\n".join(
                f"{i+1}. {s['name']} ({s['points']} pts)" 
                for i, s in enumerate(tournament_data['standings'][:5])
            )
            analysis = f"## Tournament Analysis\n\n### Top Players\n{top_players}\n\n*Note: Detailed AI analysis is currently unavailable. Please try again later.*"
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        print(f"Error generating AI analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error generating analysis: {str(e)}'
        }), 500

@tournament_bp.route('/<int:tournament_id>/teams', methods=['GET'])
@login_required
@get_db
def manage_teams(tournament_id):
    """Manage team assignments for a tournament."""
    db = g.db
    
    # Check if tournament exists and user has permission
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    # Get all players in the tournament
    players = db.get_players(tournament_id)
    
    # Separate players with and without teams
    unassigned_players = [p for p in players if not p.get('team')]
    
    # Group players by team
    teams = {}
    for player in players:
        if player.get('team'):
            team_name = player['team']
            if team_name not in teams:
                teams[team_name] = []
            teams[team_name].append(player)
    
    return render_template('tournament/manage_teams.html', 
                         tournament=tournament,
                         unassigned_players=unassigned_players,
                         teams=teams)

@tournament_bp.route('/<int:tournament_id>/assign-team/<int:player_id>', methods=['POST'])
@login_required
@get_db
def assign_team(tournament_id, player_id):
    """Assign a player to a team."""
    db = g.db
    data = request.get_json()
    team_name = data.get('team', '').strip()
    
    if not team_name:
        return jsonify({'success': False, 'message': 'Team name is required'}), 400
    
    try:
        # Update player's team
        db.cursor.execute(
            "UPDATE players SET team = ? WHERE id = ?",
            (team_name, player_id)
        )
        db.conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Team assigned successfully'
        })
    except Exception as e:
        db.conn.rollback()
        return jsonify({
            'success': False,
            'message': f'Error assigning team: {str(e)}'
        }), 500

@tournament_bp.route('/<int:tournament_id>/remove-team/<int:player_id>', methods=['POST'])
@login_required
@get_db
def remove_team(tournament_id, player_id):
    """Remove a player from their team."""
    db = g.db
    
    try:
        # Remove player's team assignment
        db.cursor.execute(
            "UPDATE players SET team = NULL WHERE id = ?",
            (player_id,)
        )
        db.conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Player removed from team'
        })
    except Exception as e:
        db.conn.rollback()
        return jsonify({
            'success': False,
            'message': f'Error removing from team: {str(e)}'
        }), 500

@tournament_bp.route('/<int:tournament_id>/create-random-teams', methods=['POST'])
@login_required
@get_db
def create_random_teams(tournament_id):
    """Create random teams for unassigned players."""
    db = g.db
    
    # Get form data
    team_size = request.form.get('team_size', type=int, default=4)
    preserve_existing = request.form.get('preserve_existing') == 'on'
    
    if team_size < 2:
        flash('Team size must be at least 2', 'danger')
        return redirect(url_for('tournament.manage_teams', tournament_id=tournament_id))
    
    try:
        # Get players to assign to teams
        if preserve_existing:
            players = db.get_players(tournament_id)
            players_to_assign = [p for p in players if not p.get('team')]
        else:
            # Clear all team assignments if not preserving existing
            db.cursor.execute("UPDATE players SET team = NULL")
            players_to_assign = db.get_players(tournament_id)
        
        # Shuffle players randomly
        random.shuffle(players_to_assign)
        
        # Create teams
        team_number = 1
        for i in range(0, len(players_to_assign), team_size):
            team_name = f"Team {team_number}"
            team_players = players_to_assign[i:i + team_size]
            
            for player in team_players:
                db.cursor.execute(
                    "UPDATE players SET team = ? WHERE id = ?",
                    (team_name, player['id'])
                )
            team_number += 1
        
        db.conn.commit()
        flash(f'Created {team_number - 1} random teams', 'success')
        
    except Exception as e:
        db.conn.rollback()
        flash(f'Error creating random teams: {str(e)}', 'danger')
    
    return redirect(url_for('tournament.manage_teams', tournament_id=tournament_id))

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
            
        # Check if user is the creator of the tournament or has a valid share link
        creator_id = tournament.get('creator_id')
        user_id = session.get('user_id')
        
        # Check for valid share token in session or URL
        share_link_key = f'share_link_{tournament_id}'
        has_valid_share_link = False
        
        # Check session first
        if share_link_key in session:
            token = session[share_link_key]
            is_valid, _ = validate_share_link(token, tournament_id)
            if is_valid:
                has_valid_share_link = True
        
        # If no valid session, check URL token
        if not has_valid_share_link:
            token = request.args.get('token')
            if token:
                is_valid, _ = validate_share_link(token, tournament_id)
                if is_valid:
                    # Store the token in session for future requests
                    session[share_link_key] = token
                    session.permanent = True
                    has_valid_share_link = True
        
        if creator_id != user_id and not has_valid_share_link:
            flash('You do not have permission to view this tournament.', 'danger')
            return redirect(url_for('tournament.index'))
            
        # Get current round and its pairings
        current_round = db.get_current_round(tournament_id)
        pairings = []
        print(current_round)
        if current_round:
            pairings = db.get_round_pairings(current_round['id'])
            
        # Get view type (individual or team)
        view_type = request.args.get('view', 'individual')
        
        # Get standings based on view type
        standings = db.get_standings(tournament_id, view_type=view_type)
        
        # Get creator's username and email
        creator_username = 'System'
        creator_email = None
        if tournament.get('creator_id'):
            from sql import SQL
            db = SQL("sqlite:///users.db")
            user = db.execute("SELECT * FROM users WHERE id = :id", id=tournament['creator_id'])

            if user:
                creator_username = user[0].get("username", 'System')
                creator_email = user[0].get("email")
        
        print(creator_username)
        from datetime import datetime
        
        return render_template('tournament/view.html', 
                            tournament=tournament,
                            current_round=current_round,
                            pairings=pairings,
                            standings=standings,
                            view_type=view_type,
                            creator_username=creator_username,
                            creator_email=creator_email,
                            now=datetime.utcnow())
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
@check_tournament_active
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

# Form for tournament settings
class TournamentSettingsForm(FlaskForm):
    # Basic info
    name = StringField('Tournament Name', validators=[DataRequired()])
    location = StringField('Location')
    start_date = StringField('Start Date (YYYY-MM-DD)', validators=[DataRequired()])
    end_date = StringField('End Date (YYYY-MM-DD)', validators=[DataRequired()])
    rounds = IntegerField('Number of Rounds', render_kw={'readonly': True})
    time_control = StringField('Time Control')
    description = TextAreaField('Description')
    comments = TextAreaField('Additional Comments', render_kw={'rows': 3}, 
                           description='Additional notes or information about the tournament')
    
    # Point settings
    win_points = FloatField('Points for a Win', default=1.0, validators=[NumberRange(min=0)])
    draw_points = FloatField('Points for a Draw', default=0.5, validators=[NumberRange(min=0)])
    loss_points = FloatField('Points for a Loss', default=0.0, validators=[NumberRange(min=0)])
    bye_points = FloatField('Points for a Bye', default=1.0, validators=[NumberRange(min=0)])
    
    submit = SubmitField('Save Changes')
    
    def validate(self, **kwargs):
        # First call the parent's validate method
        rv = FlaskForm.validate(self)
        if not rv:
            return False
            
        # Validate date format and logic
        try:
            if self.start_date.data:
                start = datetime.strptime(self.start_date.data, '%Y-%m-%d').date()
            if self.end_date.data:
                end = datetime.strptime(self.end_date.data, '%Y-%m-%d').date()
                
            if hasattr(self, 'start_date') and hasattr(self, 'end_date'):
                if start > end:
                    self.end_date.errors.append('End date must be after start date')
                    return False
                    
        except ValueError as e:
            self.start_date.errors.append('Please use YYYY-MM-DD format')
            return False
                
        return True

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

@tournament_bp.route('/<int:tournament_id>/byes', methods=['GET', 'POST'])
@login_required
@check_tournament_active
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
        
        # Get all rounds and their pairings to determine completion status
        db.cursor.execute("""
            SELECT r.id, r.round_number, 
                   COUNT(p.id) as total_pairings,
                   SUM(CASE WHEN p.result IS NOT NULL AND p.result != '' THEN 1 ELSE 0 END) as completed_pairings
            FROM rounds r
            LEFT JOIN pairings p ON r.id = p.round_id
            WHERE r.tournament_id = ?
            GROUP BY r.id, r.round_number
            ORDER BY r.round_number
        """, (tournament_id,))
        rounds_info = {}
        for r in db.cursor.fetchall():
            # A round is considered completed if it has pairings and all have results
            rounds_info[r['round_number']] = (r['total_pairings'] > 0 and 
                                            r['completed_pairings'] == r['total_pairings'])
        
        # Get current round info
        current_round = db.get_current_round(tournament_id)
        current_round_num = current_round['round_number'] if current_round else 1
        
        # Only show future rounds and current round if it's not completed
        available_rounds = []
        for i in range(1, tournament['rounds'] + 1):
            # If we have info about this round, check if it's completed
            if i in rounds_info:
                if not rounds_info[i]:  # If round is not completed
                    available_rounds.append((i, f"Round {i}"))
            # If we don't have info, it's a future round
            elif i >= current_round_num:
                available_rounds.append((i, f"Round {i}"))
        
        form.round_number.choices = available_rounds
        
        # Get current round info for the template
        current_round = db.get_current_round(tournament_id)
        current_round_num = current_round['round_number'] if current_round else 1
        
        return render_template('tournament/manage_byes.html',
                             tournament=tournament,
                             players=players,
                             byes=byes,
                             form=form,
                             current_round_num=current_round_num)
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
            
        # Get current round info
        current_round = db.get_current_round(tournament_id)
        current_round_num = current_round['round_number'] if current_round else 0
        
        # Assign the bye
        if db.assign_manual_bye(tournament_id, player_id, round_number, session['user_id']):
            # If this is the current round, regenerate pairings
            if round_number == current_round_num and current_round:
                if regenerate_current_round_pairings(db, tournament_id):
                    flash('Bye assigned and pairings updated successfully!', 'success')
                else:
                    flash('Bye assigned, but failed to update pairings. Please regenerate them manually.', 'warning')
            else:
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
        
        # Get round completion status by checking pairings
        db.cursor.execute("""
            SELECT r.id, r.round_number, 
                   COUNT(p.id) as total_pairings,
                   SUM(CASE WHEN p.result IS NOT NULL AND p.result != '' THEN 1 ELSE 0 END) as completed_pairings
            FROM rounds r
            LEFT JOIN pairings p ON r.id = p.round_id
            WHERE r.tournament_id = ? AND r.round_number = ?
            GROUP BY r.id, r.round_number
        """, (tournament_id, bye['round_number']))
        
        round_info = db.cursor.fetchone()
        
        if round_info:
            # Check if the round is completed (all pairings have results)
            is_round_completed = (round_info['total_pairings'] > 0 and 
                                round_info['completed_pairings'] == round_info['total_pairings'])
            
            if is_round_completed:
                flash('Cannot remove byes from rounds that have been completed.', 'error')
                return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
                
# Check if this is a past round (earlier than current round)
            current_round = db.get_current_round(tournament_id)
            current_round_num = current_round['round_number'] if current_round else 1
            
            if bye['round_number'] < current_round_num:
                flash('Cannot remove byes from rounds that have already been completed.', 'error')
                return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))
        
        # Get current round info
        current_round = db.get_current_round(tournament_id)
        current_round_num = current_round['round_number'] if current_round else 0
        
        # Remove the bye
        if db.remove_manual_bye(bye_id):
            # If this is the current round, regenerate pairings
            if bye['round_number'] == current_round_num and current_round:
                if regenerate_current_round_pairings(db, tournament_id):
                    flash('Bye removed and pairings updated successfully!', 'success')
                else:
                    flash('Bye removed, but failed to update pairings. Please regenerate them manually.', 'warning')
            else:
                flash('Bye removed successfully!', 'success')
        else:
            flash('Failed to remove bye. Please try again.', 'error')
        
    except Exception as e:
        print(f"Error removing bye: {e}")
        flash(f'An error occurred while removing the bye: {str(e)}', 'error')
    
    return redirect(url_for('tournament.manage_byes', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/pairings', methods=['GET', 'POST'])
@login_required
@check_tournament_active
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
    
    # Get players and current byes for the batch byes modal
    players = db.get_tournament_players(tournament_id)
    current_byes = set()
    
    if current_round:
        # Get manual byes for the current round
        byes = db.conn.execute(
            "SELECT player_id FROM manual_byes WHERE tournament_id = ? AND round_number = ?",
            (tournament_id, current_round['round_number'])
        ).fetchall()
        current_byes = {bye['player_id'] for bye in byes}
    
    # Handle form submission for completing the current round
    if request.method == 'POST' and 'complete_round' in request.form:
        # Verify the round exists and belongs to this tournament
        if not current_round:
            flash('No active round found.', 'danger')
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
            
        # Check if we have enough players to generate pairings before creating the next round
        players = db.get_tournament_players(tournament_id)
        if len(players) < 2:
            flash('Cannot generate pairings: At least 2 players are required to generate pairings.', 'error')
            return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
            
        # Create next round only if we have enough players
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
            # If we fail to generate pairings, we should clean up the round we just created
            db.conn.execute('DELETE FROM rounds WHERE id = ?', (next_round['id'],))
            db.conn.commit()
            
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
    
    from datetime import datetime
    
    return render_template(
        'tournament/pairings.html',
        tournament=tournament,
        current_round=current_round_obj,
        pairings=pairings,
        players=players,
        current_byes=current_byes,
        form=form,
        now=datetime.utcnow()
    )

@tournament_bp.route('/<int:tournament_id>/swap_players', methods=['POST'])
@login_required
def swap_players(tournament_id):
    """Swap two players in the current round's pairings."""
    data = request.get_json()
    required_fields = ['pairing1_id', 'player1_id', 'player1_color', 'pairing2_id', 'player2_id', 'player2_color']
    
    if not data or any(field not in data for field in required_fields):
        return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

    db = get_db()
    
    # Get current round
    current_round = db.get_current_round(tournament_id)
    if not current_round:
        return jsonify({'success': False, 'message': 'No active round found'}), 400
        
    if current_round['status'] == 'completed':
        return jsonify({'success': False, 'message': 'Cannot modify completed round'}), 400

    try:
        # Get the pairings
        pairing1 = db.get_pairing(data['pairing1_id'])
        pairing2 = db.get_pairing(data['pairing2_id'])
        
        if not pairing1 or not pairing2:
            return jsonify({'success': False, 'message': 'One or both pairings not found'}), 404
            
        if pairing1['round_id'] != current_round['id'] or pairing2['round_id'] != current_round['id']:
            return jsonify({'success': False, 'message': 'Pairings must be from the current round'}), 400
            
        # Get the player IDs and colors
        player1_id = int(data['player1_id'])
        player2_id = int(data['player2_id'])
        player1_color = data['player1_color']
        player2_color = data['player2_color']
        
        # Verify players are in the correct pairings and colors
        if (player1_id not in [pairing1['white_player_id'], pairing1['black_player_id']] or
            player2_id not in [pairing2['white_player_id'], pairing2['black_player_id']] or
            (player1_color == 'white' and pairing1['white_player_id'] != player1_id) or
            (player1_color == 'black' and pairing1['black_player_id'] != player1_id) or
            (player2_color == 'white' and pairing2['white_player_id'] != player2_id) or
            (player2_color == 'black' and pairing2['black_player_id'] != player2_id)):
            return jsonify({'success': False, 'message': 'Invalid player selection'}), 400
        
        # Swap the players
        with db.conn:  # Start a transaction
            # Update first pairing
            if player1_color == 'white':
                db.cursor.execute(
                    "UPDATE pairings SET white_player_id = ? WHERE id = ?",
                    (player2_id, pairing1['id'])
                )
            else:
                db.cursor.execute(
                    "UPDATE pairings SET black_player_id = ? WHERE id = ?",
                    (player2_id, pairing1['id'])
                )
            
            # Update second pairing
            if player2_color == 'white':
                db.cursor.execute(
                    "UPDATE pairings SET white_player_id = ? WHERE id = ?",
                    (player1_id, pairing2['id'])
                )
            else:
                db.cursor.execute(
                    "UPDATE pairings SET black_player_id = ? WHERE id = ?",
                    (player1_id, pairing2['id'])
                )
            
            # Clear any existing results for these pairings
            db.cursor.execute(
                "UPDATE pairings SET result = NULL WHERE id IN (?, ?)",
                (pairing1['id'], pairing2['id'])
            )
        
        return jsonify({
            'success': True,
            'message': 'Players swapped successfully',
            'pairing1_white': pairing1['white_player_id'] if player1_color != 'white' else player2_id,
            'pairing1_black': pairing1['black_player_id'] if player1_color != 'black' else player2_id,
            'pairing2_white': pairing2['white_player_id'] if player2_color != 'white' else player1_id,
            'pairing2_black': pairing2['black_player_id'] if player2_color != 'black' else player1_id
        })
        
        if black1 and black2:
            db.cursor.execute(
                "UPDATE pairings SET black_player_id = ? WHERE id = ?",
                (black2, pairing1['id'])
            )
            db.cursor.execute(
                "UPDATE pairings SET black_player_id = ? WHERE id = ?",
                (black1, pairing2['id'])
            )
        
        db.conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Players swapped successfully',
            'pairing1': {
                'id': pairing1['id'],
                'white_player_id': white2 if white1 and white2 else pairing1['white_player_id'],
                'black_player_id': black2 if black1 and black2 else pairing1['black_player_id']
            },
            'pairing2': {
                'id': pairing2['id'],
                'white_player_id': white1 if white1 and white2 else pairing2['white_player_id'],
                'black_player_id': black1 if black1 and black2 else pairing2['black_player_id']
            }
        })
        
    except Exception as e:
        db.conn.rollback()
        return jsonify({'success': False, 'message': f'Error swapping players: {str(e)}'}), 500

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
        
        # Check if this is a print view
        print_view = request.args.get('print') == '1'
        
        # Get the view type (team or individual)
        view_type = request.args.get('view', 'player')
        
        # Get the standings based on view type
        if view_type == 'team':
            standings_data = db.get_team_standings(tournament_id)
            template_name = 'team_standings.html'
        else:
            standings_data = db.get_player_standings(tournament_id)
            template_name = 'standings.html'
        
        if not standings_data:
            flash('No standings data available yet.', 'info')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
        
        # Add position numbers and format data
        for i, entry in enumerate(standings_data, 1):
            entry['position'] = i
            # Ensure all required fields have default values
            entry.setdefault('points', 0)
            entry.setdefault('buchholz', 0)
            entry.setdefault('sonneborn_berger', 0)
            entry.setdefault('rating', 0)
            entry.setdefault('team', '')
        
        # Get the current round number for display
        current_round = db.get_current_round(tournament_id)
        current_round_num = current_round['round_number'] if current_round else 0
        
        # Get current datetime for print view
        from datetime import datetime
        now = datetime.utcnow()
        
        if print_view:
            return render_template(
                'tournament/print_standings.html',
                tournament=tournament,
                standings=standings_data,
                current_round=current_round_num,
                view_type=view_type,
                now=now
            )
            
        return render_template(
            f'tournament/{template_name}',
            tournament=tournament,
            standings=standings_data,
            view_type=view_type,
            current_round=current_round_num,
            now=now
        )
        
    except Exception as e:
        print(f"Error in standings route: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred while loading the standings.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/<int:tournament_id>/rounds', methods=['GET', 'POST'])
@login_required
def rounds(tournament_id):
    """View and manage all rounds in the tournament."""
    try:
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'danger')
            return redirect(url_for('tournament.index'))
        
        # Handle adding more rounds
        if request.method == 'POST':
            try:
                additional_rounds = int(request.form.get('additional_rounds', 1))
                max_additional_rounds = 10  # Maximum number of rounds that can be added at once
                
                if additional_rounds < 1:
                    flash('Number of rounds to add must be at least 1.', 'error')
                elif additional_rounds > max_additional_rounds:
                    flash(f'You can add a maximum of {max_additional_rounds} rounds at a time.', 'error')
                else:
                    new_total = tournament['rounds'] + additional_rounds
                    max_total_rounds = 50  # Absolute maximum number of rounds
                    
                    if new_total > max_total_rounds:
                        flash(f'Maximum number of rounds ({max_total_rounds}) would be exceeded.', 'error')
                    else:
                        # Update rounds and set status to 'in_progress' if it was 'upcoming'
                        db.cursor.execute("""
                            UPDATE tournaments 
                            SET rounds = ?,
                                status = CASE WHEN status = 'upcoming' THEN 'in_progress' ELSE status END
                            WHERE id = ?
                        """, (new_total, tournament_id))
                        db.conn.commit()
                        
                        flash(f'Successfully added {additional_rounds} round(s). Total rounds is now {new_total}.', 'success')
                        return redirect(url_for('tournament.rounds', tournament_id=tournament_id))
            except ValueError:
                flash('Please enter a valid number of rounds to add.', 'error')
        
        # Get current rounds data
        rounds_data = []
        if hasattr(db, 'get_tournament_rounds'):
            rounds_data = db.get_tournament_rounds(tournament_id) or []
        
        return render_template(
            'tournament/rounds.html',
            tournament=tournament,
            rounds=rounds_data,
            prize_winners=[]
        )
    except Exception as e:
        print(f"Error in rounds route: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred while processing your request.', 'error')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

@tournament_bp.route('/round/<int:round_id>')
@login_required
def view_round(round_id):
    """View a specific round's pairings."""
    db = get_db()
    
    # Get the round data using the get_round method
    round_data = db.get_round(round_id)
    
    if not round_data:
        flash('Round not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    tournament = db.get_tournament(round_data['tournament_id'])
    pairings = db.get_pairings(round_id)
    
    # Get player details for each pairing
    for pairing in pairings:
        # The get_pairings method already includes player names and ratings
        # So we don't need to fetch them again
        if 'white_name' not in pairing and 'white_player_id' in pairing and pairing['white_player_id']:
            white = db.get_player(pairing['white_player_id'])
            if white:
                pairing['white_name'] = white.get('name', 'Unknown')
                pairing['white_rating'] = white.get('rating')
        if 'black_name' not in pairing and 'black_player_id' in pairing and pairing['black_player_id']:
            black = db.get_player(pairing['black_player_id'])
            if black:
                pairing['black_name'] = black.get('name', 'Unknown')
                pairing['black_rating'] = black.get('rating')
    
    # Check if this is a print view
    print_view = request.args.get('print') == '1'
    
    if print_view:
        return render_template(
            'tournament/print_round.html',
            tournament=tournament,
            round_number=round_data['round_number'],
            pairings=pairings,
            now=datetime.now()
        )
    
    return render_template(
        'tournament/round.html',
        tournament=tournament,
        round_data=round_data,
        pairings=pairings
    )

@tournament_bp.route('/<int:tournament_id>/conclude', methods=['POST'])
@login_required
def conclude_tournament(tournament_id):
    """Conclude a tournament and freeze all data."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    
    # Check if tournament exists and user is the creator
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
        
    if tournament['creator_id'] != session.get('user_id'):
        flash('You do not have permission to conclude this tournament.', 'danger')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))
    
    try:
        # Start transaction
        db.conn.execute('BEGIN TRANSACTION')
        
        # 1. Mark all incomplete rounds as completed
        db.cursor.execute("""
            UPDATE rounds 
            SET status = 'completed', 
                end_time = datetime('now')
            WHERE tournament_id = ? 
            AND status != 'completed'
        """, (tournament_id,))
        
        # 2. Update all pending pairings to draw if they don't have a result
        db.cursor.execute("""
            UPDATE pairings 
            SET status = 'completed',
                result = '0.5-0.5'
            WHERE status = 'pending'
            AND round_id IN (SELECT id FROM rounds WHERE tournament_id = ?)
            AND result IS NULL
        """, (tournament_id,))
        
        # 3. Update tournament status to completed
        db.cursor.execute("""
            UPDATE tournaments 
            SET status = 'completed',
                end_date = date('now')
            WHERE id = ?
        """, (tournament_id,))
        
        # Commit all changes
        db.conn.commit()
        flash('Tournament has been concluded successfully! All rounds are now finalized.', 'success')
        
    except Exception as e:
        db.conn.rollback()
        print(f"Error concluding tournament: {e}")
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

@tournament_bp.route('/mass_delete', methods=['POST'], endpoint='mass_delete')
@login_required
def mass_delete_tournaments():
    """Delete multiple tournaments at once."""
    db = get_db()
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        tournament_ids = data.get('tournament_ids', [])
        
        if not tournament_ids:
            return jsonify({'success': False, 'message': 'No tournaments selected'}), 400
        
        success_count = 0
        failed_count = 0
        failed_ids = []
        
        for tournament_id in tournament_ids:
            try:
                # Verify the tournament exists and belongs to the user
                tournament = db.get_tournament(tournament_id)
                if not tournament:
                    failed_count += 1
                    failed_ids.append(tournament_id)
                    continue
                    
                if tournament['creator_id'] != user_id:
                    failed_count += 1
                    failed_ids.append(tournament_id)
                    continue
                    
                # Delete the tournament
                if db.delete_tournament(tournament_id, user_id):
                    success_count += 1
                else:
                    failed_count += 1
                    failed_ids.append(tournament_id)
                    
            except sqlite3.IntegrityError as e:
                print(f"Integrity error deleting tournament {tournament_id}: {e}")
                failed_count += 1
                failed_ids.append(tournament_id)
                continue
            except Exception as e:
                print(f"Error deleting tournament {tournament_id}: {e}")
                failed_count += 1
                failed_ids.append(tournament_id)
                continue
        
        if success_count > 0 and failed_count == 0:
            return jsonify({
                'success': True,
                'message': f'Successfully deleted {success_count} tournament(s).'
            })
        elif failed_count > 0 and success_count == 0:
            return jsonify({
                'success': False,
                'message': f'Failed to delete {failed_count} tournament(s).',
                'failed_ids': failed_ids
            }), 400
        elif failed_count > 0 and success_count > 0:
            return jsonify({
                'success': True,
                'message': f'Successfully deleted {success_count} tournament(s). Failed to delete {failed_count} tournament(s).',
                'failed_ids': failed_ids
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No valid tournaments were selected for deletion.'
            }), 400
            
    except Exception as e:
        import traceback
        current_app.logger.error(f'Error in mass_delete_tournaments: {str(e)}\n{traceback.format_exc()}')
        return jsonify({
            'success': False,
            'message': 'An error occurred while processing your request.'
        }), 500

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

@tournament_bp.route('/<int:tournament_id>/export-pairings/<int:round_id>/<format>')
@login_required
def export_pairings(tournament_id, round_id, format):
    """Export pairings to CSV or Excel."""
    try:
        db = get_db()
        
        # Get tournament and round information
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            flash('Tournament not found.', 'danger')
            return redirect(url_for('tournament.index'))
            
        # Get pairings for the round
        pairings = db.get_pairings(round_id)
        if not pairings:
            flash('No pairings found for this round.', 'warning')
            return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))
            
        # Convert to a list of dictionaries for easier processing
        pairings_data = []
        for p in pairings:
            pairings_data.append({
                'board': p.get('board_number', ''),
                'white_name': p.get('white_name', 'BYE') if p.get('white_player_id') else 'BYE',
                'white_rating': p.get('white_rating', ''),
                'black_name': p.get('black_name', 'BYE') if p.get('black_player_id') else 'BYE',
                'black_rating': p.get('black_rating', ''),
                'result': p.get('result', '')
            })
        
        # Create a DataFrame
        import pandas as pd
        from io import BytesIO
        
        df = pd.DataFrame(pairings_data)
        
        # Create output based on format
        if format.lower() == 'xlsx':
            output = BytesIO()
            
            # Create a simple Excel file with just the data
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write the data to Excel
                df.to_excel(writer, index=False, sheet_name='Pairings')
                
                # Get the xlsxwriter objects
                workbook = writer.book
                worksheet = writer.sheets['Pairings']
                
                # Add a simple header format
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#C6E2FF',
                    'border': 1
                })
                
                # Write the column headers with the defined format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Auto-adjust column widths
                for i, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    ) + 2
                    worksheet.set_column(i, i, min(max_length, 30))
                
                # Save the workbook
                writer.close()
            
            # Rewind the buffer
            output.seek(0)
            
            # Send the file
            filename = f"{tournament['name'].replace(' ', '_')}_Round_{pairings[0].get('round_number', '')}_Pairings.xlsx"
            response = send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
            
            # Make sure to close the output buffer after sending
            response.call_on_close(output.close)
            return response
        else:  # Default to CSV
            output = BytesIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f"{tournament['name'].replace(' ', '_')}_Round_{pairings[0].get('round_number', '')}_Pairings.csv"
            )
            
    except Exception as e:
        current_app.logger.error(f'Error exporting pairings: {str(e)}')
        flash(f'Error exporting pairings: {str(e)}', 'error')
        return redirect(url_for('tournament.manage_pairings', tournament_id=tournament_id))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}

@tournament_bp.route('/<int:tournament_id>/round/<int:round_id>/batch_byes', methods=['POST'])
@login_required
@get_db
def batch_assign_byes(tournament_id, round_id):
    """Assign byes to multiple players in a batch."""
    try:
        db = g.db
        data = request.get_json()
        player_ids = data.get('player_ids', [])
        
        if not isinstance(player_ids, list):
            return jsonify({'success': False, 'message': 'Invalid player IDs format'}), 400
        
        current_round = db.get_round(round_id)
        if not current_round or current_round['tournament_id'] != tournament_id:
            return jsonify({'success': False, 'message': 'Invalid round'}), 400
        
        round_number = current_round['round_number']
        
        try:
            # Use a savepoint for the byes update
            db.cursor.execute('SAVEPOINT before_byes')
            
            # Clear existing manual byes for this round
            db.cursor.execute(
                "DELETE FROM manual_byes WHERE tournament_id = ? AND round_number = ?",
                (tournament_id, round_number)
            )
            
            # Add new manual byes
            for player_id in player_ids:
                db.cursor.execute(
                    """INSERT INTO manual_byes (tournament_id, player_id, round_number, created_by)
                    VALUES (?, ?, ?, ?)""",
                    (tournament_id, player_id, round_number, session['user_id'])
                )
            
            # Commit the byes first
            db.conn.commit()
            
            # Now generate pairings - it will handle its own transaction
            success = db.generate_pairings(tournament_id, round_id, 'swiss')
            
            if not success:
                # If pairings fail, we've already committed the byes, so just return an error
                return jsonify({
                    'success': False,
                    'message': 'Failed to generate pairings. The byes were saved but pairings could not be generated.'
                }), 500
            
            return jsonify({
                'success': True,
                'message': f'Assigned byes to {len(player_ids)} players and regenerated pairings',
                'redirect': url_for('tournament.manage_pairings', tournament_id=tournament_id)
            })
            
        except Exception as e:
            # Rollback to the savepoint if anything fails
            db.cursor.execute('ROLLBACK TO before_byes')
            db.conn.rollback()  # Ensure any changes after the savepoint are rolled back
            current_app.logger.error(f"Error in batch_byes: {e}")
            return jsonify({
                'success': False,
                'message': f'Error processing byes: {str(e)}'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in batch_assign_byes: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while processing your request'
        }), 500

@tournament_bp.route('/<int:tournament_id>/export-players')
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
    
    return send_file(
        output,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{tournament['name'].replace(' ', '_')}_players.{extension}"
    )

@tournament_bp.route('/<int:tournament_id>/export-results')
@login_required
def export_results(tournament_id):
    """Export all tournament results to a CSV or Excel file."""
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        flash('Tournament not found.', 'danger')
        return redirect(url_for('tournament.index'))
    
    try:
        # Get all rounds and their pairings
        rounds = db.get_rounds(tournament_id)
        if not rounds:
            flash('No rounds found for this tournament.', 'warning')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
            
        all_pairings = []
        
        for round_obj in rounds:
            pairings = db.get_pairings(round_obj['id'])
            if not pairings:
                continue
                
            for p in pairings:
                # Get player names, handling byes
                white_name = 'BYE'
                black_name = 'BYE'
                
                if p.get('white_player_id'):
                    white_player = db.get_player(p['white_player_id'])
                    white_name = white_player['name'] if white_player else 'Unknown Player'
                if p.get('black_player_id'):
                    black_player = db.get_player(p['black_player_id'])
                    black_name = black_player['name'] if black_player else 'Unknown Player'
                
                all_pairings.append({
                    'Round': round_obj['round_number'],
                    'Board': p.get('board_number', ''),
                    'White Player': white_name,
                    'Black Player': black_name,
                    'Result': p.get('result', '')
                })
        
        if not all_pairings:
            flash('No pairings found to export.', 'warning')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
        
        # Convert to DataFrame
        import pandas as pd
        from io import BytesIO
        
        df = pd.DataFrame(all_pairings)
        
        # Get the requested format (default to CSV)
        export_format = request.args.get('format', 'csv').lower()
        output = BytesIO()
        
        if export_format == 'xlsx':
            # Export to Excel
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
                
                # Auto-adjust column widths
                worksheet = writer.sheets['Results']
                for i, col in enumerate(df.columns):
                    max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, max_length)
                    
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            extension = 'xlsx'
        else:
            # Default to CSV
            df.to_csv(output, index=False)
            mimetype = 'text/csv'
            extension = 'csv'
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{tournament['name'].replace(' ', '_')}_results.{extension}"
        )
    
    except Exception as e:
        current_app.logger.error(f"Error exporting results: {str(e)}")
        flash('An error occurred while exporting results.', 'danger')
        return redirect(url_for('tournament.view', tournament_id=tournament_id))

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