import os
from flask import Flask, render_template, request, redirect, session, jsonify, Blueprint, url_for, flash, current_app
from flask_session import Session
from datetime import datetime, timedelta
import pytz
import secrets
from itsdangerous import URLSafeTimedSerializer
from sql import *  # Used for database connection and management
from SarvAuth import *  # Used for user authentication functions
from email_utils import send_reset_email, get_reset_token, verify_reset_token

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if session.get("name"):
        return redirect(url_for('tournament.index'))
    
    if request.method == "GET":
        return render_template("auth/login.html")
    
    # Handle POST request
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return render_template("auth/login.html", error="Username and password are required!")

    password_hash = hash(password)

    try:
        db = SQL("sqlite:///users.db")
        users = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        if not users:
            return render_template("auth/login.html", error="No account found with this username!")
            
        user = users[0]
        if user["password"] == password_hash:
            session["name"] = username
            session["user_id"] = user["id"]  # Store user_id in session
            next_page = request.args.get('next')
            return redirect(next_page or url_for('tournament.index'))

        return render_template("auth/login.html", error="Incorrect password!")
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return render_template("auth/login.html", error="An error occurred. Please try again later.")
    
@auth_blueprint.route("/signup", methods=["GET", "POST"])
def register():
    if session.get("name"):
        return redirect(url_for('tournament.index'))
        
    if request.method == "GET":
        return render_template("auth/signup.html")
    
    # Get form data
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirmpassword", "").strip()
    
    # Validate form data
    if not all([email, name, username, password, confirm_password]):
        return render_template("auth/signup.html", error="All fields are required!")
    
    if password != confirm_password:
        return render_template("auth/signup.html", error="Passwords do not match!")
    
    if len(password) < 8:
        return render_template("auth/signup.html", error="Password must be at least 8 characters long!")
    
    try:
        print("Attempting to connect to database...")
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
        db_url = f"sqlite:///{db_path}"
        print(f"Database path: {db_url}")
        
        # Test database connection
        try:
            db = SQL(db_url)
            test_query = db.execute("SELECT name FROM sqlite_master WHERE type='table';")
            print(f"Database tables: {test_query}")
            print("Database connection successful")
        except Exception as db_error:
            print(f"Database connection failed: {str(db_error)}")
            raise Exception(f"Could not connect to database: {str(db_error)}")
        
        # Check if username exists
        print(f"Checking if username '{username}' exists...")
        existing_user = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        if existing_user:
            print("Username already exists")
            return render_template("auth/signup.html", error="Username already taken!")
            
        # Check if email exists
        print(f"Checking if email '{email}' exists...")
        existing_email = db.execute("SELECT * FROM users WHERE emailAddress = :email", email=email)
        if existing_email:
            print("Email already exists")
            return render_template("auth/signup.html", error="Email already registered!")
        
        # Hash password and create user
        print("Hashing password...")
        hashed_password = hash(password)
        current_time = datetime.now(pytz.timezone("US/Eastern"))
        formatted_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        print("Preparing to insert user into database...")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Name: {name}")
        print(f"Date: {formatted_date}")
        
        # Insert new user
        try:
            db.execute(
                """
                INSERT INTO users (username, password, emailAddress, name, dateJoined)
                VALUES (:username, :password, :email, :name, :date_joined)
                """,
                username=username,
                password=hashed_password,
                email=email,
                name=name,
                date_joined=formatted_date
            )
            print("User created successfully")

            # Get the newly created user
            user = db.execute("SELECT * FROM users WHERE emailAddress = :email", email=email)
            
            if not user:
                raise Exception("Failed to retrieve user after creation")
                
            # Log the user in
            session["user_id"] = user[0]["id"]  # Access first row, then 'id' column
            session["name"] = username
            session["email"] = email
            return redirect('/tournament/')
            
        except Exception as insert_error:
            print(f"Error inserting user: {str(insert_error)}")
            return render_template("auth/signup.html", 
                                error=f"Failed to create user: {str(insert_error)}")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error during registration: {error_details}")
        return render_template("auth/signup.html", 
                             error=f"An error occurred during registration. Please try again later.")
    
@auth_blueprint.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("name"):
        return redirect(url_for('auth.login'))
    
    try:
        db = SQL("sqlite:///users.db")
        
        # Get current user data
        user = db.execute("SELECT name, emailAddress as email FROM users WHERE username = :username", 
                         username=session['name'])
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('tournament.index'))
            
        user = user[0]  # Get the first (and should be only) user
        
        if request.method == 'POST':
            # Update user information
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            
            if not name or not email:
                flash('Name and email are required', 'danger')
            else:
                # Update user in database
                db.execute("""
                    UPDATE users 
                    SET name = :name, emailAddress = :email 
                    WHERE username = :username
                """, name=name, email=email, username=session['name'])
                
                flash('Profile updated successfully!', 'success')
                # Update session if needed
                if 'email' in session:
                    session['email'] = email
                
                # Refresh user data
                user = db.execute("SELECT name, emailAddress as email FROM users WHERE username = :username", 
                                username=session['name'])[0]
        
        return render_template('auth/profile.html', user=user)
        
    except Exception as e:
        print(f"Error in profile: {str(e)}")
        flash('An error occurred while loading your profile', 'danger')
        return redirect(url_for('tournament.index'))

@auth_blueprint.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("name"):
        return redirect(url_for('auth.login'))
    
    if request.method == 'GET':
        return render_template('auth/change_password.html')
    
    try:
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Basic validation
        if not all([current_password, new_password, confirm_password]):
            flash('All fields are required', 'danger')
            return redirect(url_for('auth.change_password'))
            
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('auth.change_password'))
            
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long', 'danger')
            return redirect(url_for('auth.change_password'))
        
        db = SQL("sqlite:///users.db")
        
        # Get current user's password hash
        user = db.execute("SELECT password FROM users WHERE username = :username", 
                         username=session['name'])
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('auth.change_password'))
            
        stored_hash = user[0]['password']
        
        # Verify current password using SarvAuth
        if not checkUserPassword(session['name'], current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # Hash and update the new password using SarvAuth's hash function
        new_hash = hash(new_password)
        db.execute("""
            UPDATE users 
            SET password = :password 
            WHERE username = :username
        """, password=new_hash, username=session['name'])
        
        flash('Password updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        flash('An error occurred while changing your password', 'danger')
        return redirect(url_for('auth.change_password'))

@auth_blueprint.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handle password reset requests"""
    if request.method == 'GET':
        return render_template('auth/forgot_password.html')
    
    email = request.form.get('email', '').strip().lower()
    
    if not email:
        flash('Email is required', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    try:
        db = SQL("sqlite:///users.db")
        user = db.execute("SELECT * FROM users WHERE emailAddress = :email", email=email)
        
        if not user:
            # For security, don't reveal if the email exists or not
            flash('If an account with that email exists, a password reset link has been sent.', 'info')
            return redirect(url_for('auth.login'))
            
        user = user[0]
        
        # Generate a secure token
        token = get_reset_token(user['emailAddress'], current_app.secret_key)
        
        # Send the password reset email
        app_name = "Chess Tournament Manager"
        app_url = request.host_url.rstrip('/')
        
        send_reset_email(
            recipient_email=user['emailAddress'],
            token=token,
            app_name=app_name,
            app_url=app_url
        )
        
        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        print(f"Error in forgot_password: {str(e)}")
        flash('An error occurred. Please try again later.', 'danger')
        return redirect(url_for('auth.forgot_password'))

@auth_blueprint.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Handle password reset with a valid token"""
    # Verify the token
    email = verify_reset_token(token, current_app.secret_key)
    
    if not email:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'GET':
        return render_template('auth/reset_password.html', token=token, valid_token=True)
    
    # Handle form submission
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    # Validate the form data
    if not password or not confirm_password:
        flash('Please fill in all fields', 'danger')
        return render_template('auth/reset_password.html', token=token, valid_token=True)
        
    if password != confirm_password:
        flash('Passwords do not match', 'danger')
        return render_template('auth/reset_password.html', token=token, valid_token=True)
        
    if len(password) < 8:
        flash('Password must be at least 8 characters long', 'danger')
        return render_template('auth/reset_password.html', token=token, valid_token=True)
    
    try:
        db = SQL("sqlite:///users.db")
        user = db.execute("SELECT * FROM users WHERE emailAddress = :email", email=email)
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('auth.forgot_password'))
            
        # Update the user's password
        password_hash = hash(password)
        
        db.execute(
            "UPDATE users SET password = :password WHERE emailAddress = :email",
            password=password_hash,
            email=email
        )
        
        flash('Your password has been updated successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        print(f"Error in reset_password: {str(e)}")
        flash('An error occurred. Please try again later.', 'danger')
        return redirect(url_for('auth.forgot_password'))

@auth_blueprint.route("/profile/stats")
def user_stats():
    """Display user statistics"""
    if not session.get("name"):
        return redirect(url_for('auth.login'))
    
    try:
        # Use the users database for user lookup
        users_db = SQL("sqlite:///users.db")
        
        # Get the current user from the users database
        user = users_db.execute("SELECT * FROM users WHERE username = :username", 
                              username=session['name'])
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('auth.profile'))
            
        user_id = user[0]['id']
        
        # Use the tournament database for tournament data
        tournament_db = SQL("sqlite:///tournament.db")
        
        # Get user's tournaments with player and round counts
        tournaments = tournament_db.execute("""
            SELECT t.*, 
                   (SELECT COUNT(*) FROM tournament_players WHERE tournament_id = t.id) as player_count,
                   (SELECT COUNT(*) FROM rounds WHERE tournament_id = t.id) as round_count
            FROM tournaments t
            WHERE t.creator_id = :user_id
            ORDER BY t.created_at DESC
        """, user_id=user_id)
        
        # Calculate statistics
        stats = {
            'total_tournaments': len(tournaments),
            'total_players': sum(t.get('player_count', 0) for t in tournaments),
            'total_rounds': sum(t.get('round_count', 0) for t in tournaments)
        }
        
        # Get current time for status calculation
        current_time = datetime.utcnow().isoformat()
        
        return render_template('auth/user_stats.html', 
                             stats=stats, 
                             tournaments=tournaments,
                             current_time=current_time)
        
    except Exception as e:
        print(f"Error in user_stats: {str(e)}")
        flash('An error occurred while loading your statistics.', 'danger')
        return redirect(url_for('auth.profile'))

@auth_blueprint.route("/logout")
def logout():
    session.pop("name", None)
    return redirect('/')
