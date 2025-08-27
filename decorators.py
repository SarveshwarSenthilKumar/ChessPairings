from functools import wraps
from flask import redirect, url_for, flash, session

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
