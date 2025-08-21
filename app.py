import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from flask_session import Session
from datetime import datetime, timedelta
import pytz
from werkzeug.middleware.proxy_fix import ProxyFix

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Configure session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Create session directory if it doesn't exist
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize session
Session().init_app(app)

# Handle proxy headers if behind a reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app)

# Settings
auto_run = True
port = 5000
authentication = True

# Import blueprints
try:
    from auth import auth_blueprint
    from tournament_routes import tournament_bp
    from tournament_db import TournamentDB
    
    # Register blueprints
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    app.register_blueprint(tournament_bp, url_prefix='')
    
    print("Blueprints registered successfully")
except Exception as e:
    print(f"Error importing blueprints: {e}")

# Database configuration
def get_db_connection(db_name='tournament.db'):
    """Create and configure a thread-local database connection"""
    db_path = os.path.join(app.instance_path, db_name)
    
    if 'db' not in g:
        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    
    return g.db

def init_users_db():
    """Initialize the users database with required tables"""
    db_path = os.path.join(app.instance_path, 'users.db')
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

# Initialize database tables
def init_tournament_db():
    """Initialize the tournament database with required tables"""
    db_path = os.path.join(app.instance_path, 'tournament.db')
    if not os.path.exists(db_path):
        db = TournamentDB(db_path)
        db.create_tables()
        db.close()
        print("Tournament database initialized successfully")
    else:
        print("Tournament database already exists")

# Initialize all databases
def init_databases():
    """Initialize all required databases"""
    # Create instance directory if it doesn't exist
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Initialize tournament database
    init_tournament_db()
    
    # Initialize users database
    users_db_path = os.path.join(app.instance_path, 'users.db')
    if not os.path.exists(users_db_path):
        init_users_db()

# Initialize the application
with app.app_context():
    init_databases()

# Teardown app context to close database connection
@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Routes
@app.route('/')
def index():
    if not authentication:
        return render_template('index.html')
    if not session.get('name'):
        return render_template('index.html', authentication=True)
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
