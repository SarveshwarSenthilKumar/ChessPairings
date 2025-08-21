import os
import unittest
from app import app, db
from createDatabase import create_database

class BasicTestCase(unittest.TestCase):
    """Basic test cases for the application."""

    def setUp(self):
        """Set up test environment."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        
        # Create a fresh database for testing
        with app.app_context():
            db.create_all()

    def tearDown(self):
        """Clean up after each test."""
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_index_page(self):
        ""Test the index page.""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Chess Tournament Manager', response.data)

    def test_tournaments_page_redirects_when_not_logged_in(self):
        ""Test that the tournaments page redirects to login when not authenticated.""
        response = self.app.get('/tournaments')
        self.assertEqual(response.status_code, 302)  # Should redirect to login

    def test_404_page(self):
        ""Test the 404 error page.""
        response = self.app.get('/nonexistent-page')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Page Not Found', response.data)

if __name__ == '__main__':
    unittest.main()
