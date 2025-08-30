from flask import Blueprint, request, jsonify, render_template, url_for, redirect, flash, g, session
from functools import wraps
import json
from admin_share_links import (
    create_share_link, get_share_links, revoke_share_link,
    AVAILABLE_PERMISSIONS, share_link_required
)
from decorators import login_required, tournament_creator_required

bp = Blueprint('admin_share', __name__)

@bp.route('/share', methods=['GET'])
@login_required
def share_links(tournament_id):
    """View and manage admin share links"""
    links = get_share_links(tournament_id, session['user_id'])
    
    # Format permissions for display
    for link in links:
        link['permissions_display'] = [
            AVAILABLE_PERMISSIONS[p] 
            for p in link['permissions'] 
            if p in AVAILABLE_PERMISSIONS
        ]
    
    return render_template(
        'tournament/admin_share_links.html',
        tournament_id=tournament_id,
        links=links,
        available_permissions=AVAILABLE_PERMISSIONS
    )

@bp.route('/share/create', methods=['POST'])
@login_required
def create_link(tournament_id):
    """Create a new admin share link"""
    # Get form data
    permissions = request.form.getlist('permissions')
    expires_days = int(request.form.get('expires_days', 7))
    max_uses = request.form.get('max_uses')
    max_uses = int(max_uses) if max_uses else None
    
    if not permissions:
        flash('Please select at least one permission', 'danger')
        return redirect(url_for('admin_share.share_links', tournament_id=tournament_id))
    
    # Create the share link
    link = create_share_link(
        tournament_id=tournament_id,
        created_by=session['user_id'],
        permissions=permissions,
        expires_days=expires_days,
        max_uses=max_uses
    )
    
    if not link:
        flash('Failed to create share link', 'danger')
        return redirect(url_for('admin_share.share_links', tournament_id=tournament_id))
    
    # Generate the full share URL
    share_url = url_for(
        'tournament.view', 
        tournament_id=tournament_id, 
        token=link['token'],
        _external=True
    )
    
    flash('Share link created successfully!', 'success')
    return render_template(
        'tournament/admin_share_links.html',
        tournament_id=tournament_id,
        links=get_share_links(tournament_id, session['user_id']),
        available_permissions=AVAILABLE_PERMISSIONS,
        new_share_url=share_url
    )

@bp.route('/share/<int:link_id>/revoke', methods=['POST'])
@login_required
def revoke_link(tournament_id, link_id):
    """Revoke an admin share link"""
    success = revoke_share_link(link_id, session['user_id'])
    
    if success:
        flash('Share link has been revoked', 'success')
    else:
        flash('Failed to revoke share link', 'danger')
        
    return redirect(url_for('admin_share.share_links', tournament_id=tournament_id))

# Add a context processor to make the share_link_required decorator available to templates
@bp.app_context_processor
def inject_share_link_decorator():
    return dict(share_link_required=share_link_required)
