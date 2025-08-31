import json
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app
import sqlite3
from pathlib import Path

# Define available permissions and their descriptions
AVAILABLE_PERMISSIONS = {
    'can_edit_settings': 'Can edit tournament settings',
    'can_manage_players': 'Can add/remove players',
    'can_manage_rounds': 'Can manage rounds and pairings',
    'can_enter_results': 'Can enter match results',
    'can_view_reports': 'Can view tournament reports'
}

def get_db_connection():
    db_path = Path(__file__).parent / 'tournament.db'
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def create_share_link(tournament_id, created_by, permissions, expires_days=7, max_uses=None):
    """Create a new admin share link.
    
    Args:
        tournament_id: ID of the tournament
        created_by: User ID of the link creator
        permissions: List of permission strings
        expires_days: Number of days until the link expires (None for no expiration)
        max_uses: Maximum number of uses (None for unlimited)
    
    Returns:
        dict: The created share link data or None if failed
    """
    # Validate permissions
    invalid_perms = set(permissions) - set(AVAILABLE_PERMISSIONS.keys())
    if invalid_perms:
        raise ValueError(f"Invalid permissions: {', '.join(invalid_perms)}")
    
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat() if expires_days else None
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_share_links 
            (tournament_id, token, permissions, created_by, expires_at, max_uses)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            tournament_id,
            token,
            json.dumps(permissions),
            created_by,
            expires_at,
            max_uses
        ))
        conn.commit()
        
        # Return the created link
        return {
            'id': cursor.lastrowid,
            'tournament_id': tournament_id,
            'token': token,
            'permissions': permissions,
            'created_by': created_by,
            'expires_at': expires_at,
            'max_uses': max_uses,
            'use_count': 0,
            'is_active': True
        }
    except sqlite3.Error as e:
        current_app.logger.error(f"Error creating share link: {e}")
        return None
    finally:
        conn.close()

def validate_share_link(token, tournament_id):
    """Validate a share link and return permissions if valid.
    
    Args:
        token: The share token to validate
        tournament_id: The tournament ID to validate against
        
    Returns:
        tuple: (is_valid, permissions) where permissions is a list of permissions if valid
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM admin_share_links 
            WHERE token = ? AND tournament_id = ? 
            AND is_active = 1 
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            AND (max_uses IS NULL OR use_count < max_uses)
        ''', (token, tournament_id))
        
        link = cursor.fetchone()
        if not link:
            return False, None
            
        # Update use count
        cursor.execute('''
            UPDATE admin_share_links 
            SET use_count = use_count + 1 
            WHERE id = ?
        ''', (link['id'],))
        conn.commit()
        
        return True, json.loads(link['permissions'])
        
    except Exception as e:
        current_app.logger.error(f"Error validating share link: {e}")
        return False, None
    finally:
        conn.close()

def get_share_links(tournament_id, user_id):
    """Get all share links for a tournament (only for tournament creator)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.*, u.username as creator_username
            FROM admin_share_links l
            JOIN users u ON l.created_by = u.id
            WHERE l.tournament_id = ? AND l.created_by = ?
            ORDER BY l.created_at DESC
        ''', (tournament_id, user_id))
        
        links = []
        for row in cursor.fetchall():
            links.append({
                'id': row['id'],
                'token': row['token'],
                'permissions': json.loads(row['permissions']),
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'max_uses': row['max_uses'],
                'use_count': row['use_count'],
                'is_active': bool(row['is_active']),
                'creator_username': row['creator_username']
            })
        return links
        
    except Exception as e:
        current_app.logger.error(f"Error getting share links: {e}")
        return []
    finally:
        conn.close()

def revoke_share_link(link_id, user_id):
    """Revoke a share link (set is_active = 0)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Verify the user owns this link
        cursor.execute('''
            SELECT id FROM admin_share_links 
            WHERE id = ? AND created_by = ?
        ''', (link_id, user_id))
        
        if not cursor.fetchone():
            return False
            
        # Revoke the link
        cursor.execute('''
            UPDATE admin_share_links 
            SET is_active = 0 
            WHERE id = ?
        ''', (link_id,))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        current_app.logger.error(f"Error revoking share link: {e}")
        return False
    finally:
        conn.close()

def share_link_required(permission=None):
    """Decorator to check for valid share link with required permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import session, redirect, url_for, flash
            
            # If user is already logged in, use their normal permissions
            if 'user_id' in session:
                return f(*args, **kwargs)
                
            # Check for share token in query params
            token = request.args.get('token')
            if not token:
                flash('Share token is required', 'danger')
                return redirect(url_for('auth.login'))
                
            # Get tournament_id from route
            tournament_id = kwargs.get('tournament_id')
            if not tournament_id:
                flash('Invalid tournament', 'danger')
                return redirect(url_for('tournament.index'))
                
            # Validate token
            is_valid, permissions = validate_share_link(token, tournament_id)
            if not is_valid:
                flash('Invalid or expired share link', 'danger')
                return redirect(url_for('tournament.index'))
                
            # Check if specific permission is required
            if permission and permission not in permissions:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('tournament.index'))
                
            # Store permissions in session for this request
            g.share_link_permissions = permissions
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator