from flask import Flask, render_template, request, redirect, session, url_for, Response, make_response, g
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, generate_csrf
from auth import auth_blueprint
from tournament_routes import tournament_bp
from SarvAuth import *
from sql import *
from datetime import datetime, date
import simplejson as json
import secrets

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
    app.run(debug=True, port=5000)
