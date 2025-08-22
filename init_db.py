import os
import sqlite3

def init_db():
    # Remove existing database if it exists
    if os.path.exists('users.db'):
        os.remove('users.db')
    
    # Create new database
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Create users table with proper schema
    c.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        emailAddress TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        dateJoined TEXT NOT NULL,
        accountStatus TEXT DEFAULT 'active',
        role TEXT DEFAULT 'user',
        twoFactorAuth INTEGER DEFAULT 0,
        salt TEXT,
        lastLogin TEXT,
        phoneNumber TEXT,
        dateOfBirth TEXT,
        gender TEXT
    )
    ''')
    
    # Create indexes for better performance
    c.execute('CREATE INDEX idx_username ON users(username)')
    c.execute('CREATE INDEX idx_email ON users(emailAddress)')
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()
