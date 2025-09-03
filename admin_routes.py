from flask import Blueprint, render_template, redirect, url_for, flash, current_app, session, jsonify
from functools import wraps
import sqlite3
import os
from flask_session import Session

def get_db_connection(db_name='tournament.db'):
    try:
        # Try root path first, then instance path
        db_path = os.path.join(current_app.root_path, db_name)
        if not os.path.exists(db_path):
            db_path = os.path.join(current_app.instance_path, db_name)
            
        current_app.logger.info(f"Attempting to connect to database at: {db_path}")
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        current_app.logger.info(f"Successfully connected to {db_name}")
        return conn
    except Exception as e:
        current_app.logger.error(f"Error connecting to {db_name}: {str(e)}")
        raise

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/dashboard')
def dashboard():
    total_users = 0
    recent_users = []
    total_tournaments = 0
    active_tournaments = 0
    recent_tournaments = []
    
    try:
        # Get users from users.db using SQL class
        current_app.logger.info("Fetching users data...")
        try:
            from sql import SQL
            db = SQL("sqlite:///users.db")
            
            # Get total users(
            print(db.execute("SELECT * FROM users"))
            result = db.execute("SELECT COUNT(*) as count FROM users")
            total_users = result[0]['count'] if result else 0
            current_app.logger.info(f"Found {total_users} total users")
            
            # Get recent users with name and email
            recent_users = db.execute('''
                SELECT id, username, name, emailAddress as email 
                FROM users 
                ORDER BY id DESC 
                LIMIT 5
            ''')
            current_app.logger.info(f"Fetched {len(recent_users)} recent users")
            
        except Exception as e:
            current_app.logger.error(f"Error fetching users: {str(e)}")
            flash('Error loading user data', 'danger')
        
        # Get tournaments from tournament.db using SQL class
        current_app.logger.info("Fetching tournaments data...")
        try:
            from sql import SQL
            db = SQL("sqlite:///tournament.db")
            
            # Get total tournaments
            result = db.execute("SELECT COUNT(*) as count FROM tournaments")
            total_tournaments = result[0]['count'] if result else 0
            current_app.logger.info(f"Found {total_tournaments} total tournaments")
            
            # Get active tournaments (in progress)
            result = db.execute("""
                SELECT COUNT(*) as count 
                FROM tournaments 
                WHERE status = 'ongoing' OR status = 'in_progress' OR status = 'In Progress'
            """)
            active_tournaments = result[0]['count'] if result else 0
            current_app.logger.info(f"Found {active_tournaments} active tournaments")
            
            # Get recent tournaments
            recent_tournaments = db.execute("""
                SELECT id, name, created_at, status 
                FROM tournaments 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            current_app.logger.info(f"Fetched {len(recent_tournaments)} recent tournaments")
            
        except Exception as e:
            current_app.logger.error(f"Error fetching tournaments: {str(e)}")
            flash('Error loading tournament data', 'danger')
        
    except Exception as e:
        current_app.logger.error(f"Error in dashboard: {str(e)}")
        flash('Error loading dashboard data', 'danger')
        return redirect(url_for('index'))
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_tournaments=total_tournaments,
                         active_tournaments=active_tournaments,
                         recent_tournaments=recent_tournaments,
                         recent_users=recent_users)

@admin_bp.route('/api/users')
def get_all_users():
    try:
        from sql import SQL
        
        # Connect to users database using SQL class
        db = SQL("sqlite:///users.db")
        
        # Get all users with relevant fields
        users = db.execute("""
            SELECT 
                id, 
                username, 
                emailAddress as email, 
                name,
                dateJoined as created_at,
                role,
                accountStatus as status
            FROM users 
            ORDER BY id DESC
        """)
        
        current_app.logger.info(f"Retrieved {len(users)} users from database")
        return jsonify(users)
        
    except Exception as e:
        current_app.logger.error(f"Error getting users: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to load users. Please check server logs for details."}), 500

@admin_bp.route('/api/tournaments')
def get_all_tournaments():
    # For testing, allow any user to access the API
    # if session.get("name") != "sarveshwarsenthilkumar":
    #     return jsonify({"error": "Unauthorized"}), 403
        
    try:
        conn = get_db_connection('tournament.db')
        tournaments = conn.execute('''
            SELECT id, name, created_at, status 
            FROM tournaments 
            ORDER BY created_at DESC
        ''').fetchall()
        conn.close()
        return jsonify([dict(t) for t in tournaments])
    except Exception as e:
        current_app.logger.error(f"Error getting tournaments: {str(e)}")
        return jsonify({"error": "Failed to load tournaments"}), 500

@admin_bp.route('/api/debug/users')
def debug_users():
    """Debug endpoint to check users table structure and data"""
    try:
        from sql import SQL
        db = SQL("sqlite:///users.db")
        
        # Get table info
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        users_columns = db.execute("PRAGMA table_info(users)")
        
        # Get sample data
        sample_users = db.execute("SELECT * FROM users LIMIT 5")
        
        return jsonify({
            "tables": tables,
            "users_columns": users_columns,
            "sample_users": sample_users
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add more admin routes as needed
