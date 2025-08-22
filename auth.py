import os
from flask import Flask, render_template, request, redirect, session, jsonify, Blueprint, url_for
from flask_session import Session
from datetime import datetime
import pytz
from sql import * #Used for database connection and management
from SarvAuth import * #Used for user authentication functions

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
            next_page = request.args.get('next')
            return redirect(next_page or '/tournament/')

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
            
            # Log the user in
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
    
@auth_blueprint.route("/logout")
def logout():
    session.pop("name", None)
    return redirect('/')
