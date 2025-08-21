
import os
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_session import Session
from datetime import datetime, timedelta
import pytz
from sql import *  # Used for database connection and management
from SarvAuth import *  # Used for user authentication functions
from auth import auth_blueprint
from tournament_routes import tournament_bp

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
app.config['SECRET_KEY'] = os.urandom(24)  # For session management

# Initialize session
Session(app)

# Settings
auto_run = True  # Auto-run the server when app.py is executed
port = 5000  # Default port
authentication = True  # Enable/disable authentication

# Register blueprints
if authentication:
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

# Register tournament blueprint
app.register_blueprint(tournament_bp)

# Database configuration
def get_db_connection(db_name='tournament.db'):
    """Create and configure a thread-local database connection"""
    import sqlite3
    from flask import g
    
    db_path = os.path.join(app.root_path, 'instance', db_name)
    
    if 'db' not in g:
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False  # Allow multiple threads to access the connection
        )
        g.db.row_factory = sqlite3.Row
    
    return g.db

# Initialize database tables
def init_tournament_db():
    from tournament_db import TournamentDB
    db_path = os.path.join(app.root_path, 'instance', 'tournament.db')
    db = TournamentDB(db_path)
    db.create_tables()
    db.close()

def init_users_db():
    db_path = os.path.join(app.root_path, 'instance', 'users.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize databases on first run
def init_databases():
    # Create instance directory if it doesn't exist
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
    
    # Initialize tournament database
    tournament_db_path = os.path.join(app.root_path, 'instance', 'tournament.db')
    if not os.path.exists(tournament_db_path):
        init_tournament_db()
    
    # Initialize users database
    users_db_path = os.path.join(app.root_path, 'instance', 'users.db')
    if not os.path.exists(users_db_path):
        init_users_db()

# Run database initialization
init_databases()

# Teardown app context to close database connection
@app.teardown_appcontext
def close_db(exception):
    from flask import g
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Base route
@app.route("/")
def index():
    if not authentication:
        return render_template("index.html")
    else:
        if not session.get("name"):
            return render_template("index.html", authentication=True)
        else:
            return redirect(url_for('tournament.index'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error='Internal server error'), 500

if __name__ == '__main__':
    if auto_run:
        app.run(debug=True, port=port)
