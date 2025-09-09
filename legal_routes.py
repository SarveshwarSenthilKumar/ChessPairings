from flask import Blueprint, render_template

legal_bp = Blueprint('legal', __name__, template_folder='templates')

@legal_bp.route('/terms')
def terms():
    return render_template('legal/terms.html')

@legal_bp.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')
