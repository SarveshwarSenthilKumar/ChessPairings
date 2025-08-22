from flask import Flask, render_template, request, redirect, session, url_for
from flask_session import Session
from auth import auth_blueprint
from tournament_routes import tournament_bp
from SarvAuth import *
from sql import *
from datetime import datetime

# Create Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize session
Session(app)

def format_datetime(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ""
    if isinstance(value, str):
        # Try to parse the string into a datetime object
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                value = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return value
    return value.strftime(format)

# Register the filter with Jinja2
app.jinja_env.filters['datetimeformat'] = format_datetime

# Register blueprints
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(tournament_bp, url_prefix='/tournament')

# Routes
@app.route("/")
def index():
    if not session.get("name"):
        return render_template("index.html", authentication=True)
    return redirect("/tournament/")

if __name__ == '__main__':
    app.config['DEBUG'] = True
    app.run(debug=True, port=5000)
