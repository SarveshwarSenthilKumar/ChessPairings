from functools import wraps
from flask import Flask, render_template, request, redirect, session, jsonify, Blueprint, url_for, flash, current_app, g
from flask_session import Session
from datetime import datetime
import pytz
import sqlite3
import os
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Blueprint
auth_blueprint = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to ensure a user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    """Get a database connection from the application context."""
    if 'db' not in g:
        db_path = os.path.join(current_app.root_path, 'instance', 'users.db')
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False  # Allow multiple threads to access the connection
        )
        g.db.row_factory = sqlite3.Row
    return g.db

@auth_blueprint.teardown_request
def teardown_db(exception=None):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_users_db():
    """Initialize the users database with the required tables."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Create users table with additional fields for user information
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        
        db.commit()
        print("✅ Users database initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Error initializing users database: {str(e)}")
        return False

# Initialize the database when this module is imported
init_users_db()

@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
        
    if request.method == "GET":
        return render_template("auth/login.html")
    
    try:
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()
        
        if not username or not password:
            flash("Username and password are required", "error")
            return render_template("auth/login.html"), 400
            
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if user is None:
            flash("Invalid username or password", "error")
            return render_template("auth/login.html"), 401
            
        # In a real app, you should use proper password hashing
        if user["password"] != password:  # This is just for example - use proper password hashing in production
            flash("Invalid username or password", "error")
            return render_template("auth/login.html"), 401
            
        # Update last login
        db.execute(
            'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
            (user['id'],)
        )
        db.commit()
        
        # Store user info in session
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        
        flash("You have been logged in successfully!", "success")
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        flash("An error occurred during login. Please try again.", "error")
        return render_template("error.html", error="An error occurred during login"), 500
    
@auth_blueprint.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        return redirect(url_for("index"))
        
    if request.method == "GET":
        return render_template("auth/signup.html")
    
    try:
        # Get form data
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        
        # Validate input
        if not all([username, email, password, confirm_password, first_name, last_name]):
            flash("All fields are required", "error")
            return render_template("auth/signup.html"), 400
            
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("auth/signup.html"), 400
            
        if len(password) < 8:
            flash("Password must be at least 8 characters long", "error")
            return render_template("auth/signup.html"), 400
            
        # Get database connection
        db = get_db()
        
        # Check if username or email already exists
        existing_user = db.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        if existing_user:
            flash("Username or email already exists", "error")
            return render_template("auth/signup.html"), 400
            
        # In a real app, you should hash the password before storing it
        # hashed_password = generate_password_hash(password)
        
        try:
            # Insert new user
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO users (username, email, password, first_name, last_name) VALUES (?, ?, ?, ?, ?)',
                (username, email, password, first_name, last_name)  # Use hashed_password in production
            )
            db.commit()
            
            # Get the new user's ID
            user = db.execute(
                'SELECT id, username FROM users WHERE username = ?', (username,)
            ).fetchone()
            
            # Store user info in session
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            
            flash("Account created successfully!", "success")
            return redirect(url_for("index"))
            
        except sqlite3.IntegrityError as e:
            db.rollback()
            flash("An error occurred while creating your account. The username or email might already be taken.", "error")
            return render_template("auth/signup.html"), 400
            
    except Exception as e:
        current_app.logger.error(f"Signup error: {str(e)}")
        flash("An error occurred during signup. Please try again.", "error")
        return render_template("error.html", error="An error occurred during signup"), 500

@auth_blueprint.route("/logout")
def logout():
    """Log the user out and clear their session."""
    if 'user_id' in session:
        session.clear()
        flash("You have been successfully logged out.", "success")
    return redirect(url_for("index"))
