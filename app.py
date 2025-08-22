
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from auth import auth_blueprint
from tournament_routes import tournament_bp
from SarvAuth import *
from sql import *

# Create Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize session
Session(app)

# Register blueprints
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(tournament_bp, url_prefix='/tournament')

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("name"):
        return render_template("index.html", authentication=True)
    return render_template("/auth/loggedin.html")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
