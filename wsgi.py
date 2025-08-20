""
WSGI config for Chess Tournament Manager.

This module contains the WSGI application used by the production server.
It exposes the WSGI callable as a module-level variable named 'application'.
"""
import os
from app import app

# Set the environment to production
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_ENV'] = 'production'

# This is the application object that will be used by any WSGI server
application = app

if __name__ == "__main__":
    # This is only used when running the application directly with Python
    application.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
