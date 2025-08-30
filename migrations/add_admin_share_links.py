import sqlite3
import secrets
from pathlib import Path

def add_admin_share_links():
    db_path = Path(__file__).parent.parent / 'tournament.db'
    print(f"Database path: {db_path.absolute()}")
    print(f"Database exists: {db_path.exists()}")
    
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        print("Connected to database successfully")
        
        # Check if tournaments table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tournaments'")
        if not cursor.fetchone():
            print("Error: 'tournaments' table does not exist")
            return False
            
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Error: 'users' table does not exist")
            return False
        
        # Create admin_share_links table
        print("Creating admin_share_links table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_share_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            permissions TEXT NOT NULL,  -- JSON string of permissions
            created_by INTEGER NOT NULL,  -- User ID who created the link
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_uses INTEGER,  -- NULL for unlimited uses
            use_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )''')
        
        # Create an index for faster lookups
        print("Creating index...")
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_admin_share_links_token 
        ON admin_share_links(token)
        ''')
        
        conn.commit()
        print("Successfully created admin_share_links table and index")
        
        # Verify the table was created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_share_links'")
        if cursor.fetchone():
            print("Verification: admin_share_links table exists")
        else:
            print("Warning: admin_share_links table not found after creation")
            
        return True
        
    except sqlite3.Error as e:
        print(f"SQLite Error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Starting migration...")
    success = add_admin_share_links()
    import sys
    sys.exit(0 if success else 1)
