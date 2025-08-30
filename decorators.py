from functools import wraps
from flask import redirect, url_for, flash, session, request, g

def login_required(f):
    """Decorator to ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            next_url = request.url if request.method == 'GET' else ''
            return redirect(url_for('auth.login', next=next_url))
        return f(*args, **kwargs)
    return decorated_function

def tournament_creator_required(f):
    """Decorator to ensure user is the creator of the tournament."""
    @wraps(f)
    def decorated_function(tournament_id, *args, **kwargs):
        from tournament_routes import get_db
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        
        if not tournament:
            flash('Tournament not found.', 'danger')
            return redirect(url_for('tournament.index'))
            
        if str(tournament.get('created_by')) != str(session.get('user_id')):
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
            
        return f(tournament_id, *args, **kwargs)
    return decorated_function

def check_tournament_active(f):
    """Decorator to check if a tournament is active (not completed)."""
    @wraps(f)
    def decorated_function(tournament_id, *args, **kwargs):
        from tournament_routes import get_db
        db = get_db()
        tournament = db.get_tournament(tournament_id)
        
        if tournament and tournament.get('status') == 'completed':
            flash('This tournament has been concluded and can no longer be modified.', 'warning')
            return redirect(url_for('tournament.view', tournament_id=tournament_id))
            
        return f(tournament_id, *args, **kwargs)
    return decorated_function
