import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, url_for

def get_reset_token(email, secret_key):
    """Generate a secure token for password reset"""
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, secret_key, expiration=3600):
    """Verify the reset token and return the email if valid"""
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        email = serializer.loads(
            token,
            salt='password-reset-salt',
            max_age=expiration
        )
        return email
    except:
        return None

def send_reset_email(recipient_email, token, app_name, app_url):
    """Send a password reset email to the user"""
    # This is a simplified version that prints to console
    # In production, you would use a real email service
    reset_url = f"{app_url}/reset-password/{token}"
    
    subject = f"{app_name} - Password Reset Request"
    body = f"""
    You requested a password reset for your {app_name} account.
    
    Please click the following link to reset your password:
    {reset_url}
    
    If you didn't request this, please ignore this email.
    The link will expire in 1 hour.
    """
    
    # In a real application, you would send an actual email here
    print("="*50)
    print(f"To: {recipient_email}")
    print(f"Subject: {subject}")
    print("\n" + body.strip())
    print("="*50)
    
    return True
