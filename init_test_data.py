"""
Script to initialize the application with test data for development and testing.
"""
import os
import sys
import random
from datetime import datetime, timedelta
from faker import Faker
from sql import *

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Initialize Faker for generating fake data
fake = Faker()

def create_test_users():
    """Create test users with different roles."""
    # Create admin user if not exists
    if not get_user_by_username('admin'):
        create_user('admin', 'admin@example.com', 'admin123', 'admin')
        print("Created admin user")
    
    # Create arbiter user if not exists
    if not get_user_by_username('arbiter'):
        create_user('arbiter', 'arbiter@example.com', 'arbiter123', 'arbiter')
        print("Created arbiter user")
    
    # Create regular users
    for i in range(1, 6):
        username = f'user{i}'
        if not get_user_by_username(username):
            create_user(username, f'{username}@example.com', 'password123', 'user')
    print("Created test users")

def create_test_players(count=20):
    """Create test players with random ratings."""
    players = []
    for _ in range(count):
        first_name = fake.first_name()
        last_name = fake.last_name()
        rating = random.randint(1000, 2800)
        title = random.choice([None, 'GM', 'IM', 'FM', 'CM', 'WGM', 'WIM', 'WFM', 'WCM'])
        
        player = {
            'first_name': first_name,
            'last_name': last_name,
            'rating': rating,
            'title': title,
            'fide_id': f"{random.randint(100000, 999999)}",
            'country': fake.country_code(),
            'created_at': datetime.utcnow()
        }
        
        # Insert player into database
        query = """
        INSERT INTO players (first_name, last_name, rating, title, fide_id, country, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            player['first_name'],
            player['last_name'],
            player['rating'],
            player['title'],
            player['fide_id'],
            player['country'],
            player['created_at']
        )
        
        cursor = get_db().cursor()
        cursor.execute(query, params)
        player_id = cursor.lastrowid
        get_db().commit()
        
        players.append({
            'id': player_id,
            **player
        })
    
    print(f"Created {len(players)} test players")
    return players

def create_test_tournament():
    """Create a test tournament with rounds and pairings."""
    # Create a test tournament
    tournament_data = {
        'name': 'Test Chess Tournament',
        'description': 'A test tournament with sample data',
        'start_date': datetime.utcnow() + timedelta(days=1),
        'end_date': datetime.utcnow() + timedelta(days=3),
        'location': 'Online',
        'time_control': '90+30',
        'rounds': 5,
        'status': 'scheduled',
        'created_by': 1  # Admin user
    }
    
    # Insert tournament into database
    query = """
    INSERT INTO tournaments (name, description, start_date, end_date, location, 
                           time_control, rounds, status, created_at, created_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
    """
    params = (
        tournament_data['name'],
        tournament_data['description'],
        tournament_data['start_date'],
        tournament_data['end_date'],
        tournament_data['location'],
        tournament_data['time_control'],
        tournament_data['rounds'],
        tournament_data['status'],
        tournament_data['created_by']
    )
    
    cursor = get_db().cursor()
    cursor.execute(query, params)
    tournament_id = cursor.lastrowid
    get_db().commit()
    
    print(f"Created test tournament with ID {tournament_id}")
    
    # Get all players to add to the tournament
    cursor.execute("SELECT id, rating FROM players ORDER BY rating DESC")
    players = cursor.fetchall()
    
    # Add players to the tournament
    for i, player in enumerate(players):
        cursor.execute("""
        INSERT INTO tournament_players (tournament_id, player_id, seed, initial_rating, current_rating)
        VALUES (?, ?, ?, ?, ?)
        """, (tournament_id, player['id'], i + 1, player['rating'], player['rating']))
    
    get_db().commit()
    print(f"Added {len(players)} players to the tournament")
    
    return tournament_id

def main():
    """Main function to initialize test data."""
    print("Initializing test data...")
    
    # Create test users
    create_test_users()
    
    # Create test players
    players = create_test_players(20)
    
    # Create a test tournament
    tournament_id = create_test_tournament()
    
    print("\nTest data initialization complete!")
    print("You can now log in with the following accounts:")
    print("- Username: admin, Password: admin123 (Admin user)")
    print("- Username: arbiter, Password: arbiter123 (Arbiter user)")
    print("- Username: user1-5, Password: password123 (Regular users)")
    print(f"\nTest tournament ID: {tournament_id}")

if __name__ == "__main__":
    main()
