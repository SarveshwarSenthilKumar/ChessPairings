from flask import Flask, render_template, request, redirect, session, url_for, Response, make_response, g
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, generate_csrf
from auth import auth_blueprint
from tournament_routes import tournament_bp
from public_routes import public_bp
from admin_share_routes import bp as admin_share_bp
from admin_routes import admin_bp as admin_blueprint
from dev_routes import init_dev_routes
from stats_routes import stats_bp
from legal_routes import legal_bp
from SarvAuth import *
from sql import *
from datetime import datetime, date
import simplejson as json
import secrets
from markupsafe import Markup
import re

# Custom JSON provider
class CustomJSONProvider:
    def dumps(self, obj, **kwargs):
        def default(o):
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
        return json.dumps(obj, default=default, **kwargs)
    
    def loads(self, s, **kwargs):
        return json.loads(s, **kwargs)

# Create Flask app
app = Flask(__name__)

# Helper function to return JSON responses
def json_response(data, status=200):
    response = make_response(
        json.dumps(data, default=str, ignore_nan=True, ensure_ascii=False),
        status
    )
    response.mimetype = 'application/json'
    return response

# Configuration
app.config['SECRET_KEY'] = 'your-secure-secret-key-123'  # Use a fixed key for development
app.config['DATABASE'] = 'tournament.db'  # Path to the SQLite database
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = 'your-csrf-secret-key-123'  # Fixed key for development
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour

# Initialize session
Session(app)

# Configure CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Make CSRF token available in all templates
@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf}

# Disable CSRF for specific endpoints if needed
# csrf.exempt(json_response)

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

def ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f"{n}{suffix}"

def nl2br(value):
    """Convert newlines to <br> tags in text."""
    if value is None:
        return ''
    return Markup(value.replace('\n', '<br>'))

# Context processor to make available routes accessible in all templates
@app.context_processor
def inject_routes():
    def has_route(route_name):
        return route_name in [str(rule.endpoint) for rule in app.url_map.iter_rules()]
    return dict(has_route=has_route)

# Register the filters with Jinja2
app.jinja_env.filters['datetimeformat'] = format_datetime
app.jinja_env.filters['ordinal'] = ordinal
app.jinja_env.filters['nl2br'] = nl2br

# Register blueprints
app.register_blueprint(auth_blueprint)
app.register_blueprint(admin_blueprint, url_prefix='/admin')
app.register_blueprint(tournament_bp, url_prefix='/tournament')
app.register_blueprint(public_bp, url_prefix='/public')
app.register_blueprint(stats_bp, url_prefix='/stats')
app.register_blueprint(legal_bp, url_prefix='/legal')

# Ensure debug mode is enabled for development routes
app.debug = True

# Initialize development routes
init_dev_routes(app)

app.register_blueprint(admin_share_bp, url_prefix='/tournament/<int:tournament_id>/admin')

# Routes
@app.route("/")
def index():
    if not session.get("name"):
        return render_template("index.html", authentication=True)
    return redirect("/tournament/")

@app.route("/team")
def team():
    return render_template("team.html")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
