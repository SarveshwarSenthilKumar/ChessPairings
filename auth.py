from flask import Flask, render_template, request, redirect, session, jsonify, Blueprint
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
    email = request.form.get("emailaddress", "").strip().lower()
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
        db = SQL("sqlite:///users.db")
        
        # Check if username exists
        existing_user = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        if existing_user:
            return render_template("auth/signup.html", error="Username already taken!")
            
        # Check if email exists
        existing_email = db.execute("SELECT * FROM users WHERE email = :email", email=email)
        if existing_email:
            return render_template("auth/signup.html", error="Email already registered!")
        
        # Hash password and create user
        hashed_password = hash(password)
        db.execute(
            """
            INSERT INTO users (username, password, email, name, date_created)
            VALUES (:username, :password, :email, :name, :date_created)
            """,
            username=username,
            password=hashed_password,
            email=email,
            name=name,
            date_created=datetime.now(pytz.timezone("US/Eastern"))
        )
        
        # Log the user in
        session["name"] = username
        return redirect('/tournament/')
        
    except Exception as e:
        print(f"Error during registration: {str(e)}")
        return render_template("auth/signup.html", 
                             error="An error occurred during registration. Please try again.")
    
@auth_blueprint.route("/logout")
def logout():
    session.pop("name", None)
    return redirect('/')
