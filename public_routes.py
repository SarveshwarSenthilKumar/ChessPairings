import json
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_file, g, request, jsonify, make_response
from flask_wtf.csrf import generate_csrf
from functools import wraps
import io
from datetime import datetime
from tournament_db import TournamentDB
import pandas as pd
from io import BytesIO

# Create blueprint
public_bp = Blueprint('public', __name__, template_folder='templates')

def get_db():
    """Get a database connection."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', 'tournament.db')
        g.db = TournamentDB(db_path)
    return g.db

def public_tournament_required(f):
    """Decorator to check if the tournament exists and is accessible via share token."""
    @wraps(f)
    def decorated_function(token, *args, **kwargs):
        db = get_db()
        tournament = db.get_tournament_by_share_token(token)
        if not tournament:
            if request.args.get('format') == 'json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Invalid or expired tournament link'}), 404
            flash('Invalid or expired tournament link.', 'error')
            return redirect(url_for('index'))
        return f(tournament, *args, **kwargs)
    return decorated_function

@public_bp.route('/t/<token>')
@public_bp.route('/tournament/<token>')  # Adding an additional route for backward compatibility
def view_tournament(token):
    """Public view of a tournament."""
    view_type = request.args.get('view', 'player')  # Get view type from query params
    db = get_db()
    tournament = db.get_tournament_by_share_token(token)
    
    if not tournament:
        flash('Invalid or expired tournament link.', 'error')
        return redirect(url_for('index'))
    
    # Get tournament data based on view type
    if view_type == 'team':
        standings = db.get_team_standings(tournament['id'])
    else:
        standings = db.get_standings(tournament['id'])
        
    current_round = db.get_current_round(tournament['id'])
    pairings = db.get_round_pairings(current_round['id']) if current_round else []
    rounds = db.get_tournament_rounds(tournament['id'])
    
    return render_template(
        'tournament/public_view.html',
        tournament=tournament,
        standings=standings,
        current_round=current_round,
        pairings=pairings,
        rounds=rounds,
        view_type=view_type,
        now=datetime.utcnow(),
        db=db
    )

# These routes are relative to the blueprint's url_prefix ('/public')
# Debug route to test player history response
@public_bp.route('/debug/player/history')
def debug_player_history():
    """Debug endpoint to test player history response."""
    test_data = {
        'success': True,
        'player': {'id': 1, 'name': 'Test Player', 'rating': 1500},
        'history': [
            {'opponent': 'Opponent 1', 'result': '1-0', 'color': 'white', 'round': 1},
            {'opponent': 'Opponent 2', 'result': '0-1', 'color': 'black', 'round': 2}
        ],
        'tournament': {'id': 1, 'name': 'Test Tournament'},
        'player_stats': {'wins': 1, 'losses': 1, 'draws': 0, 'points': 1.0}
    }
    return jsonify(test_data)

@public_bp.route('/t/<token>/player/<int:player_id>/history')
@public_bp.route('/tournament/<token>/player/<int:player_id>/history')
@public_tournament_required
def player_history(tournament, player_id):
    """Get player's match history for public view."""
    print(f"\n=== Player History Request ===")
    print(f"Tournament ID: {tournament['id']}")
    print(f"Player ID: {player_id}")
    print(f"Tournament Token: {tournament.get('share_token')}")
    
    db = get_db()
    
    # Get player info
    player = db.get_player(player_id)
    if not player:
        print(f"Player {player_id} not found in database")
        if request.args.get('format') == 'json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Player not found'}), 404
        return "Player not found", 404
        
    print(f"Found player: {player['name']} (ID: {player_id})")
    
    # Get player's history
    print("\nFetching player history...")
    history = db.get_player_history(player_id)
    print(f"Retrieved {len(history)} matches for player {player_id}")
    
    # Get player's current tournament stats
    print("\nFetching tournament standings...")
    standings = db.get_standings(tournament['id'])
    player_stats = next((p for p in standings if p['id'] == player_id), None)
    
    if player_stats:
        print(f"Player stats in current tournament: {player_stats}")
    else:
        print(f"Player {player_id} not found in current tournament standings")
    
    # Always return JSON for this endpoint since it's only used via AJAX
    response_data = {
        'success': True,
        'player': dict(player) if player else None,
        'history': history,  # This is already a list of dicts from get_player_history
        'tournament': dict(tournament) if tournament else None,
        'player_stats': dict(player_stats) if player_stats else None
    }
    
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, 'isoformat'):  # Handle datetime objects
                return obj.isoformat()
            elif hasattr(obj, '__dict__'):  # Handle SQLAlchemy model instances
                return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
            return str(obj)  # Convert anything else to string
    
    response = make_response(
        json.dumps(response_data, cls=CustomJSONEncoder, ensure_ascii=False),
        200
    )
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response

@public_bp.route('/t/<token>/export/<format>')
@public_tournament_required
def public_export(tournament, format):
    """Export tournament data in the specified format."""
    db = get_db()
    
    # Get tournament data
    standings = db.get_standings(tournament['id'])
    rounds = db.get_tournament_rounds(tournament['id'])
    
    if format == 'pdf':
        # This is a placeholder - you'll need to implement PDF generation
        # For now, we'll return a CSV as an example
        output = BytesIO()
        
        # Create a simple CSV with standings
        data = [
            ['Rank', 'Name', 'Points', 'Buchholz', 'Sonneborn-Berger']
        ]
        
        for i, player in enumerate(standings, 1):
            data.append([
                i,
                player['name'],
                f"{player.get('score', 0):.1f}",
                f"{player.get('buchholz', 0):.1f}",
                f"{player.get('sonneborn_berger', 0):.1f}"
            ])
        
        # Convert to DataFrame and then to CSV
        df = pd.DataFrame(data[1:], columns=data[0])
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{tournament['name']}_standings.csv",
            mimetype='text/csv'
        )
        
    elif format == 'xlsx':
        # Create Excel file with multiple sheets
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Standings sheet
            standings_data = []
            for i, player in enumerate(standings, 1):
                standings_data.append({
                    'Rank': i,
                    'Name': player['name'],
                    'Points': player.get('score', 0),
                    'Buchholz': player.get('buchholz', 0),
                    'Sonneborn-Berger': player.get('sonneborn_berger', 0)
                })
            
            if standings_data:
                df_standings = pd.DataFrame(standings_data)
                df_standings.to_excel(writer, sheet_name='Standings', index=False)
            
            # Rounds and pairings
            for round_info in rounds:
                pairings = db.get_round_pairings(round_info['id'])
                if pairings:
                    pairings_data = []
                    for p in pairings:
                        pairings_data.append({
                            'Board': p.get('board_number', ''),
                            'White': p.get('white_name', 'BYE'),
                            'Black': p.get('black_name', 'BYE'),
                            'Result': p.get('result', '-')
                        })
                    
                    df_round = pd.DataFrame(pairings_data)
                    sheet_name = f"Round {round_info['round_number']}"
                    df_round.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{tournament['name']}_export.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    flash('Invalid export format.', 'error')
    return redirect(url_for('public.public_tournament_view', token=tournament['share_token']))

# Add this to your app.py:
# from public_routes import public_bp
# app.register_blueprint(public_bp, url_prefix='/public')
