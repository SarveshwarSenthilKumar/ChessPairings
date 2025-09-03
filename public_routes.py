import json
import os
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_file, g, request, jsonify, make_response
from flask_wtf.csrf import generate_csrf
from functools import wraps
import io
from dotenv import load_dotenv
from datetime import datetime
from tournament_db import TournamentDB
import pandas as pd
from io import BytesIO
import openai

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    def decorated_function(*args, **kwargs):
        token = kwargs.get('token')
        if not token:
            return jsonify({'success': False, 'error': 'Missing tournament token'}), 400
            
        db = get_db()
        tournament = db.get_tournament_by_share_token(token)
        if not tournament:
            if request.args.get('format') == 'json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Invalid or expired tournament link'}), 404
            flash('Invalid or expired tournament link.', 'error')
            return redirect(url_for('index'))
        
        # Pass through the player_id if it exists in kwargs
        player_id = kwargs.get('player_id')
        if player_id is not None:
            return f(tournament, player_id)
        return f(tournament)
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
    """Get a player's match history in a tournament."""
    db = get_db()
    
    # Get player info
    player = db.get_player(player_id)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    
    # Get tournament for additional context
    tournament_id = tournament['id']
    
    # Get match history with detailed stats
    try:
        history = db.get_player_match_history(tournament_id, player_id)
    except Exception as e:
        print(f"Error getting player match history: {e}")
        return jsonify({'error': 'Failed to retrieve match history'}), 500
    
    # Get player's current tournament stats
    standings = db.get_standings(tournament_id)
    player_stats = next((p for p in standings if p['id'] == player_id), None)
    
    # Prepare response with player info, matches, and stats
    response = {
        'success': True,
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
        'matches': history.get('matches', []),
        'stats': history.get('stats', {}),
        'tournament_stats': player_stats
    }
    
    return jsonify(response)

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

@public_bp.route('/t/<token>/ai-analysis', methods=['GET'])
@public_tournament_required
def ai_analysis(tournament):
    """Generate an AI analysis of the tournament."""
    print(f"[DEBUG] AI Analysis - Received request for tournament: {tournament.get('name')}")
    print(f"[DEBUG] Tournament data: {tournament}")
    
    if not tournament:
        print("[ERROR] No tournament found for the given token")
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
        
    db = get_db()
    tournament_id = tournament['id']
    print(f"[DEBUG] Processing tournament ID: {tournament_id}")
    
    try:
        
        # Get tournament data
        players = db.get_players(tournament_id)
        if not players:
            return jsonify({
                'success': False,
                'error': 'No players found in this tournament'
            })
            
        print(f"[DEBUG] Players data: {players}")
        
        # Ensure all players have required fields
        for player in players:
            if 'name' not in player:
                player['name'] = 'Unknown Player'
            if 'rating' not in player:
                player['rating'] = 'Unrated'
            
        rounds = db.get_rounds(tournament_id)
        if not rounds:
            return jsonify({
                'success': False,
                'error': 'No rounds found in this tournament'
            })
            
        pairings = []
        for round_ in rounds:
            round_pairings = db.get_pairings(round_['id'])
            print(f"[DEBUG] Round {round_['round_number']} pairings: {round_pairings}")
            
            for pairing in round_pairings:
                # Ensure all required fields are present
                if 'white_player' not in pairing:
                    pairing['white_player'] = 'Unknown Player'
                if 'black_player' not in pairing:
                    pairing['black_player'] = 'Unknown Player'
                if 'result' not in pairing:
                    pairing['result'] = '*'  # Default to ongoing game
                    
                pairing['round_number'] = round_['round_number']
                pairings.append(pairing)
                
        print(f"[DEBUG] All pairings: {pairings}")
    
        # Get standings
        standings = db.get_standings(tournament_id)
        if not standings:
            return jsonify({
                'success': False,
                'error': 'Could not generate tournament standings'
            })
            
        print(f"[DEBUG] Standings data: {standings}")
        
        # Ensure all standings have required fields
        for i, standing in enumerate(standings, 1):
            if 'rank' not in standing:
                standing['rank'] = i
        
        # Prepare data for AI
        tournament_data = {
            'name': tournament['name'],
            'status': tournament['status'],
            'start_date': tournament['start_date'],
            'end_date': tournament.get('end_date', 'Ongoing'),
            'total_players': len(players),
            'total_rounds': len(rounds),
            'players': [{
                'name': p['name'],
                'rating': p.get('rating'),
                'team': p.get('team_name')
            } for p in players],
            'standings': [{
                'rank': s['rank'],
                'name': s['name'],
                'points': s['points'],
                'tiebreak1': s.get('tiebreak1', 0),
                'tiebreak2': s.get('tiebreak2', 0)
            } for s in standings],
            'pairings': [{
                'round': p['round_number'],
                'white': next((pl['name'] for pl in players if pl['id'] == p['white_player_id']), 'Unknown'),
                'black': next((pl['name'] for pl in players if pl['id'] == p['black_player_id']), 'Unknown') if p['black_player_id'] else 'Bye',
                'result': p.get('result', 'Not played')
            } for p in pairings]
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
        
        # Call OpenAI API with the latest model
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
