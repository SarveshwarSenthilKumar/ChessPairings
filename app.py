
import os
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_session import Session
from datetime import datetime
import pytz
from sql import *  # Used for database connection and management
from SarvAuth import *  # Used for user authentication functions
from auth import auth_blueprint
from tournament_routes import tournament_bp

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

# Ensure the instance folder exists
os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

# Initialize database
def init_db():
    from tournament_db import TournamentDB
    db = TournamentDB(os.path.join(app.root_path, 'instance', 'tournament.db'))
    db.create_tables()
    db.close()

# Initialize database on first run
if not os.path.exists(os.path.join(app.root_path, 'instance', 'tournament.db')):
    init_db()

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
