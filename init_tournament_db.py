import os
from tournament_db import TournamentDB

def init_tournament_db():
    """Initialize the tournament database with empty tables."""
    # Remove existing database if it exists
    if os.path.exists('tournament.db'):
        os.remove('tournament.db')
    
    # Initialize the database (this will create the tables)
    db = TournamentDB('tournament.db')
    db.close()
    
    print("Tournament database initialized with empty tables.")

if __name__ == "__main__":
    init_tournament_db()
