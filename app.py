
from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for, g
from flask_session import Session
from datetime import datetime, timedelta
import pytz
import os
import sqlite3
from functools import wraps

# Import blueprints
from auth import auth_blueprint
from tournament import tournament_bp

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config.update(
    SECRET_KEY=os.urandom(24),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_PERMANENT=True,
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_session'),
    DATABASE='tournament.db',
    USERS_DATABASE='users.db'
)

# Ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize session
Session(app)

# Configuration variables
auto_run = True  # Change to False if you don't want the server to start automatically
port = 5000  # Port to run the server on
authentication = True  # Set to False to disable authentication

def get_db(db_name='tournament'):
    """Helper function to get a database connection."""
    db = getattr(g, f'_{db_name}_db', None)
    if db is None:
        db_path = app.config['DATABASE'] if db_name == 'tournament' else app.config['USERS_DATABASE']
        db = g._tournament_db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        
        # Enable foreign key support
        db.execute('PRAGMA foreign_keys = ON;')
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection at the end of the request."""
    db = getattr(g, '_tournament_db', None)
    if db is not None:
        db.close()
    
    users_db = getattr(g, '_users_db', None)
    if users_db is not None:
        users_db.close()

def init_db():
    """Initialize the database with required tables."""
    # This will be handled by init_db.py
    print("Database initialization is handled by init_db.py")
    print("Please run 'python init_db.py' to initialize the databases.")

# Register blueprints
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(tournament_bp, url_prefix='')

# Custom error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

# Context processor to make variables available to all templates
@app.context_processor
def inject_user():
    user_data = {}
    if 'name' in session:
        user_data['username'] = session['name']
        # Add any other user data you want to make available in templates
    return dict(user=user_data)

# Main route
@app.route("/")
def index():
    if not authentication:
        return render_template("index.html")
    
    if not session.get("name"):
        return render_template("index.html", authentication=True)
    
    # Redirect to tournaments list if user is logged in
    return redirect(url_for('tournament.list_tournaments'))

def init_db():
    """Initialize the database with required tables."""
    from sql import SQL
    import os
    
    # Create users database if it doesn't exist
    if not os.path.exists('users.db'):
        db = SQL("sqlite:///users.db")
        db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            name TEXT,
            dateJoined TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
        """)
    
    # Create tournament database if it doesn't exist
    if not os.path.exists('tournament.db'):
        db = SQL("sqlite:///tournament.db")
        with open('database_schema.sql', 'r') as f:
            schema = f.read()
        # Split the schema into individual statements and execute them
        for statement in schema.split(';'):
            if statement.strip():
                db.execute(statement.strip())

# Run the application
if __name__ == '__main__' and auto_run:
    # Initialize databases
    init_db()
    
    # Run the Flask app
    app.run(debug=True, port=port, host='0.0.0.0')
