from flask import Blueprint, render_template, jsonify, send_file, make_response, current_app, session, redirect, url_for, request
from datetime import datetime as dt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import io
import os
from tournament_db import TournamentDB
from decorators import check_tournament_active
from functools import wraps

def check_tournament_permission(permission):
    """Decorator to check if user has the required tournament permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(tournament_id, *args, **kwargs):
            db = get_db()
            
            # Get user_id from the decorated function's arguments or session
            user_id = kwargs.get('user_id')
            if not user_id and 'user_id' in session:
                user_id = session['user_id']
                
            if not user_id:
                return redirect(url_for('auth.login'))
                
            # Check if user is the tournament creator
            tournament = db.get_tournament(tournament_id)
            if not tournament:
                return "Tournament not found", 404
                
            if tournament['creator_id'] == user_id:
                return f(tournament_id, *args, **kwargs)
                
            # Check admin permissions
            admin = db.get_tournament_admin(tournament_id, user_id)
            if admin and admin.get(permission, False):
                return f(tournament_id, *args, **kwargs)
                
            # Check share link permissions if any
            from flask import request
            share_token = request.args.get('token')
            if share_token:
                from admin_share_links import validate_share_link
                share_link = validate_share_link(tournament_id, share_token)
                if share_link and share_link.get(permission, False):
                    return f(tournament_id, *args, **kwargs)
            
            return "You don't have permission to view this page", 403
        return decorated_function
    return decorator

# Create blueprint
stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/user/<int:user_id>')
def user_stats(user_id):
    """Display user statistics page."""
    try:
        from sql import SQL
        db = SQL("sqlite:///users.db")
        
        # Get user info
        user = db.execute("SELECT * FROM users WHERE id = :id", id=user_id)
        if not user:
            return "User not found", 404
            
        user = user[0]
        
        # Get user's tournaments with player and round counts
        from sql import SQL
        tournament_db = SQL("sqlite:///tournament.db")
        
        tournaments = tournament_db.execute("""
            SELECT t.*, 
                   (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count,
                   (SELECT COUNT(*) FROM rounds WHERE tournament_id = t.id) as round_count
            FROM tournaments t
            WHERE t.creator_id = :user_id
            ORDER BY t.created_at DESC
        """, user_id=user_id)
        
        # Calculate basic stats
        total_tournaments = len(tournaments)
        total_players = sum(t.get('player_count', 0) for t in tournaments)
        
        # Calculate rounds info
        total_rounds = 0
        completed_rounds = 0
        
        for t in tournaments:
            tournament_rounds = t.get('rounds', 0)
            tournament_completed = t.get('round_count', 0)
            
            total_rounds += tournament_rounds
            completed_rounds += min(tournament_completed, tournament_rounds)  # Cap at total rounds
        
        # Calculate creator-specific stats
        current_time = dt.utcnow()
        completed_tournaments = 0
        in_progress_tournaments = 0
        upcoming_tournaments = 0
        
        for t in tournaments:
            status = str(t.get('status', '')).lower()
            end_date_str = t.get('end_date')
            start_date_str = t.get('start_date')
            
            try:
                end_date = dt.fromisoformat(end_date_str) if end_date_str else None
                start_date = dt.fromisoformat(start_date_str) if start_date_str else None
                
                if status == 'completed' or (end_date and end_date < current_time):
                    completed_tournaments += 1
                elif status == 'in_progress' or (start_date and start_date <= current_time):
                    in_progress_tournaments += 1
                else:
                    upcoming_tournaments += 1
            except Exception as e:
                current_app.logger.error(f"Error processing tournament dates: {e}")
                # Default to upcoming if there's an error with date parsing
                upcoming_tournaments += 1
        
        # Calculate completion percentage (avoid division by zero)
        completion_rate = (completed_tournaments / total_tournaments * 100) if total_tournaments > 0 else 0
        
        # Get recent tournaments (last 3)
        recent_tournaments = sorted(tournaments, key=lambda x: x.get('created_at', ''), reverse=True)[:3]
        
        # Calculate average participants
        avg_participants = round(total_players / total_tournaments, 1) if total_tournaments > 0 else 0
        
        # Format the member since date
        from datetime import datetime
        
        def format_date(date_str):
            if not date_str:
                return 'N/A'
            try:
                # If it's already a datetime object
                if isinstance(date_str, datetime):
                    return date_str.strftime('%B %d, %Y')
                # If it's a string, try to parse it
                if isinstance(date_str, str):
                    # Try different date formats
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                        try:
                            dt = datetime.strptime(date_str.split('.')[0], fmt)
                            return dt.strftime('%B %d, %Y')
                        except ValueError:
                            continue
                return 'N/A'
            except Exception:
                return 'N/A'
        
        # Prepare data for template
        member_since = format_date(user.get('dateJoined') or user.get('created_at'))
        stats = {
            # Basic stats
            'total_tournaments': total_tournaments,
            'total_players': total_players,
            'total_rounds': total_rounds,
            'completed_rounds': completed_rounds,
            'member_since': member_since,
            
            # Creator-specific stats
            'completed_tournaments': completed_tournaments,
            'in_progress_tournaments': in_progress_tournaments,
            'upcoming_tournaments': upcoming_tournaments,
            'completion_rate': round(completion_rate, 1),
            'avg_participants': avg_participants,
            'recent_tournaments': [{
                'id': t.get('id'),
                'name': t.get('name', 'Unnamed Tournament'),
                'status': t.get('status', 'unknown').replace('_', ' ').title(),
                'player_count': t.get('player_count', 0),
                'created_at': format_date(t.get('created_at'))
            } for t in recent_tournaments]
        }
        
        # Ensure user has all required fields
        user_info = {
            'username': user.get('username', 'User'),
            'emailAddress': user.get('emailAddress')
        }
        
        return render_template('stats/user_stats.html', 
                             stats=stats,
                             user=user_info,
                             tournaments=tournaments[:5])  # Show only recent 5 tournaments
    except Exception as e:
        current_app.logger.error(f"Error in user_stats: {str(e)}")
        return "An error occurred while loading user statistics.", 500

def get_db():
    """Get a database connection."""
    db_path = os.path.join(current_app.root_path, 'tournament.db')
    return TournamentDB(db_path)

def get_standings_data(tournament_id):
    """Get tournament standings data as a DataFrame."""
    db = get_db()
    standings = db.get_standings(tournament_id)
    return pd.DataFrame(standings)

def get_pairings_data(tournament_id):
    """Get all pairings data as a DataFrame."""
    db = get_db()
    rounds = db.get_rounds(tournament_id)
    
    all_pairings = []
    for round_info in rounds:
        pairings = db.get_pairings(round_info['id'])
        for pairing in pairings:
            pairing['round_number'] = round_info['round_number']
            all_pairings.append(pairing)
    
    return pd.DataFrame(all_pairings)

@stats_bp.route('/tournament/<int:tournament_id>/stats')
@check_tournament_active
@check_tournament_permission('can_view_reports')
def tournament_stats(tournament_id, **kwargs):
    """Display tournament statistics dashboard."""
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    
    if not tournament:
        return "Tournament not found", 404
    
    # Check if the tournament has any rounds
    rounds = db.get_rounds(tournament_id)
    if not rounds:
        return render_template('tournament/no_rounds.html', tournament=tournament)
    
    # Get standings data
    standings = db.get_standings(tournament_id)
    completed_rounds = [r for r in rounds if r.get('completed')]
    
    # Count total games
    total_games = 0
    for r in completed_rounds:
        pairings = db.get_pairings(r['id'])
        total_games += len([p for p in pairings if p.get('result')])
    
    # Generate visualizations
    performance_chart = generate_performance_chart(tournament_id)
    score_distribution = generate_score_distribution(tournament_id)
    results_chart = generate_results_chart(tournament_id)
    
    return render_template('tournament/stats.html',
                         tournament=tournament,
                         standings=standings,
                         completed_rounds=completed_rounds,
                         total_games=total_games,
                         performance_chart=performance_chart,
                         score_distribution=score_distribution,
                         results_chart=results_chart)

@stats_bp.route('/tournament/<int:tournament_id>/graphical-stats')
@check_tournament_active
@check_tournament_permission('can_view_reports')
def graphical_stats(tournament_id):
    """Display graphical tournament statistics dashboard."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    
    if not tournament:
        return "Tournament not found", 404
        
    # Get additional data needed for the graphical view
    rounds = db.get_rounds(tournament_id)
    if not rounds:
        return render_template('tournament/no_rounds.html', tournament=tournament)
    
    # Get standings and player data
    standings = db.get_standings(tournament_id)
    players = db.get_players(tournament_id)
    
    # Get recent games
    recent_games = []
    for r in sorted(rounds, key=lambda x: x['round_number'], reverse=True):
        pairings = db.get_pairings(r['id'])
        for p in pairings:
            if p.get('result'):
                white = next((player for player in players if player['id'] == p['white_player_id']), None)
                black = next((player for player in players if player['id'] == p['black_player_id']), None)
                if white and black:
                    recent_games.append({
                        'round': r['round_number'],
                        'white': white['name'],
                        'black': black['name'],
                        'result': p['result'],
                        'date': p.get('updated_at') or r.get('end_date')
                    })
        if len(recent_games) >= 10:  # Limit to 10 most recent games
            break
    
    # Calculate game results distribution
    results = {'1-0': 0, '0-1': 0, '1/2-1/2': 0, '1-0F': 0, '0-1F': 0, '1/2-1/2F': 0}
    for r in rounds:
        pairings = db.get_pairings(r['id'])
        for p in pairings:
            if p.get('result') in results:
                results[p['result']] += 1
    
    # Prepare data for the graphical view
    stats = {
        'tournament': {
            'id': tournament['id'],
            'name': tournament['name'],
            'status': tournament.get('status', 'upcoming'),
            'start_date': tournament.get('start_date'),
            'end_date': tournament.get('end_date'),
            'rounds': len(rounds),
            'completed_rounds': len([r for r in rounds if r.get('completed')]),
            'players': len(players),
            'games_played': sum(1 for r in rounds for p in db.get_pairings(r['id']) if p.get('result'))
        },
        'standings': standings[:10],  # Top 10 players
        'recent_games': recent_games[:10],
        'results': results,
        'top_performers': [],
        'points_progression': {}
    }
    
    # Calculate points progression for top 5 players
    top_players = [p['name'] for p in standings[:5]]
    for player in top_players:
        stats['points_progression'][player] = []
        for r in sorted(rounds, key=lambda x: x['round_number']):
            points = 0
            pairings = db.get_pairings(r['id'])
            for p in pairings:
                white = next((pl for pl in players if pl['id'] == p.get('white_player_id')), None)
                black = next((pl for pl in players if pl['id'] == p.get('black_player_id')), None)
                
                if white and white['name'] == player and p.get('result'):
                    if p['result'] == '1-0' or p['result'] == '1-0F':
                        points += 1
                    elif p['result'] == '1/2-1/2' or p['result'] == '1/2-1/2F':
                        points += 0.5
                elif black and black['name'] == player and p.get('result'):
                    if p['result'] == '0-1' or p['result'] == '0-1F':
                        points += 1
                    elif p['result'] == '1/2-1/2' or p['result'] == '1/2-1/2F':
                        points += 0.5
            stats['points_progression'][player].append(points)
    
    # Add top performers with their stats
    for i, player in enumerate(standings[:5]):
        stats['top_performers'].append({
            'rank': i + 1,
            'name': player['name'],
            'points': player.get('points', 0),
            'wins': player.get('wins', 0),
            'losses': player.get('losses', 0),
            'draws': player.get('draws', 0),
            'performance': player.get('performance', 0)
        })
    
    return render_template('tournament/graphical_stats.html', 
                         tournament=tournament,
                         stats=stats)

def generate_performance_chart(tournament_id):
    """Generate a line chart showing player performance over rounds."""
    db = get_db()
    
    # Get all rounds for the tournament
    rounds = db.get_rounds(tournament_id)
    if not rounds:
        return None
    
    # Get current standings to identify top players
    current_standings = db.get_standings(tournament_id)
    if not current_standings:
        return None
    
    # Get top 5 players
    top_players = [player['name'] for player in current_standings[:5]]
    
    # Create a figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Track player points by round
    player_points = {player: [] for player in top_players}
    
    # For each round, get the standings up to that round
    for round_num in range(1, len(rounds) + 1):
        # Get all pairings up to this round
        all_pairings = []
        for r in rounds:
            if r['round_number'] > round_num:
                continue
            round_pairings = db.get_pairings(r['id'])
            for p in round_pairings:
                p['round_number'] = r['round_number']
                all_pairings.append(p)
        
        # Calculate points for each player up to this round
        points = {player: 0 for player in top_players}
        for pairing in all_pairings:
            if not pairing['result'] or pairing.get('is_bye'):
                continue
                
            white_player = pairing['white_name']
            black_player = pairing['black_name']
            result = pairing['result']
            
            if white_player in points and result:
                if result == '1-0':
                    points[white_player] += 1
                elif result == '0-1' and black_player in points:
                    points[black_player] += 1
                elif result == '0.5-0.5':
                    points[white_player] += 0.5
                    if black_player in points:
                        points[black_player] += 0.5
            
        # Store points for this round
        for player in top_players:
            player_points[player].append({
                'round': round_num,
                'points': points[player]
            })
    
    # Add traces for each player
    for player in top_players:
        if player_points[player]:  # Only add if we have data for this player
            df_player = pd.DataFrame(player_points[player])
            fig.add_trace(
                go.Scatter(
                    x=df_player['round'],
                    y=df_player['points'],
                    name=player,
                    mode='lines+markers',
                    line=dict(width=2)
                ),
                secondary_y=False
            )
    
    # Update layout
    fig.update_layout(
        title='Top 5 Players Performance by Round',
        xaxis_title='Round',
        yaxis_title='Points',
        hovermode='closest',
        showlegend=True,
        height=500
    )
    
    return fig.to_html(full_html=False)

def generate_score_distribution(tournament_id):
    """Generate a histogram of score distribution."""
    df = get_standings_data(tournament_id)
    
    if df.empty:
        return None
    
    fig = px.histogram(
        df, 
        x='points',
        nbins=10,
        title='Score Distribution',
        labels={'points': 'Points'},
        opacity=0.8,
        color_discrete_sequence=['#1f77b4']
    )
    
    fig.update_layout(
        xaxis_title='Points',
        yaxis_title='Number of Players',
        showlegend=False,
        height=400
    )
    
    return fig.to_html(full_html=False)

def generate_results_chart(tournament_id):
    """Generate a pie chart of game results (wins/draws/losses)."""
    db = get_db()
    pairings = get_pairings_data(tournament_id)
    
    if pairings.empty:
        return None
    
    # Filter out byes and unplayed games
    results = pairings[
        (pairings['result'] != '') & 
        (pairings['result'] != 'bye') & 
        (pairings['result'] != 'half-point-bye')
    ]
    
    if results.empty:
        return None
    
    # Count results
    result_counts = results['result'].value_counts().reset_index()
    result_counts.columns = ['result', 'count']
    
    # Map result codes to human-readable labels
    result_map = {
        '1-0': 'White Win',
        '0-1': 'Black Win',
        '1/2-1/2': 'Draw',
        '1-0F': 'White Forfeit Win',
        '0-1F': 'Black Forfeit Win',
        '1/2-1/2F': 'Forfeit Draw'
    }
    
    result_counts['result'] = result_counts['result'].map(
        lambda x: result_map.get(x, x)
    )
    
    fig = px.pie(
        result_counts,
        values='count',
        names='result',
        title='Game Results Distribution',
        hole=0.3
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        marker=dict(line=dict(color='#FFFFFF', width=2))
    )
    
    fig.update_layout(
        showlegend=False,
        height=400
    )
    
    return fig.to_html(full_html=False)

@stats_bp.route('/tournament/<int:tournament_id>/export/stats')
@check_tournament_active
@check_tournament_permission('can_view_reports')
def export_stats(tournament_id, **kwargs):
    """Export all statistics as a PDF report."""
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    
    import plotly.io as pio
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from io import BytesIO
    
    db = get_db()
    tournament = db.get_tournament(tournament_id)
    
    if not tournament:
        return "Tournament not found", 404
    
    # Create a PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=72)
    
    # Container for the 'Flowable' objects
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=1))
    
    # Add title
    elements.append(Paragraph(f"Tournament Report: {tournament['name']}", 
                           styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Generate charts
    charts = [
        ('Performance Over Rounds', generate_performance_chart(tournament_id)),
        ('Score Distribution', generate_score_distribution(tournament_id)),
        ('Game Results', generate_results_chart(tournament_id))
    ]
    
    # Add charts to PDF
    for title, chart_html in charts:
        if not chart_html:
            continue
            
        # Convert Plotly HTML to image
        fig = pio.from_json(chart_html)
        img_bytes = pio.to_image(fig, format='png')
        img = Image(BytesIO(img_bytes), width=6*inch, height=4*inch)
        
        elements.append(Paragraph(title, styles['Heading2']))
        elements.append(Spacer(1, 12))
        elements.append(img)
        elements.append(Spacer(1, 24))
    
    # Build the PDF
    doc.build(elements)
    
    # File response
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.mimetype = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=tournament_{tournament_id}_report.pdf'
    
    return response
