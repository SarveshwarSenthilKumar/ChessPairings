from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_file, g
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
            flash('Invalid or expired tournament link.', 'error')
            return redirect(url_for('index'))
        return f(tournament, *args, **kwargs)
    return decorated_function

@public_bp.route('/t/<token>')
@public_bp.route('/tournament/<token>')  # Adding an additional route for backward compatibility
def view_tournament(token):
    """Public view of a tournament."""
    db = get_db()
    tournament = db.get_tournament_by_share_token(token)
    
    if not tournament:
        flash('Invalid or expired tournament link.', 'error')
        return redirect(url_for('index'))
    
    # Get tournament data
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
        view_type='player',  # Default to individual view
        now=datetime.utcnow(),  # Add current timestamp
        db=db  # Add database object to template context
    )

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
