import sqlite3
import secrets
from pathlib import Path

def add_share_token():
    db_path = Path(__file__).parent.parent / 'tournament.db'
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if tournaments table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tournaments';
        """)
        if not cursor.fetchone():
            print("Tournaments table doesn't exist. Please run the main database setup first.")
            return False
            
        # Check if share_token column exists
        cursor.execute("""
            SELECT COUNT(*) FROM pragma_table_info('tournaments') 
            WHERE name='share_token';
        """)
        
        if cursor.fetchone()[0] == 0:
            # First add the column without the UNIQUE constraint
            cursor.execute("""
                ALTER TABLE tournaments 
                ADD COLUMN share_token TEXT;
            """)
            
            # Generate tokens for existing tournaments
            cursor.execute("SELECT id FROM tournaments")
            for (tournament_id,) in cursor.fetchall():
                cursor.execute(
                    "UPDATE tournaments SET share_token = ? WHERE id = ?",
                    (secrets.token_urlsafe(16), tournament_id)
                )
            
            # Now add the UNIQUE constraint
            try:
                cursor.execute("""
                    CREATE UNIQUE INDEX idx_tournaments_share_token ON tournaments(share_token);
                """)
            except sqlite3.OperationalError as e:
                print(f"Warning: Could not add unique constraint: {e}")
                print("This is likely because there are duplicate tokens. Regenerating...")
                
                # If there are duplicates, regenerate all tokens and try again
                cursor.execute("SELECT id, share_token FROM tournaments")
                tournaments = cursor.fetchall()
                
                # Create a set to track used tokens
                used_tokens = set()
                
                for tournament_id, token in tournaments:
                    if token in used_tokens or not token:
                        new_token = secrets.token_urlsafe(16)
                        while new_token in used_tokens:
                            new_token = secrets.token_urlsafe(16)
                        cursor.execute(
                            "UPDATE tournaments SET share_token = ? WHERE id = ?",
                            (new_token, tournament_id)
                        )
                        used_tokens.add(new_token)
                    else:
                        used_tokens.add(token)
                
                # Try adding the unique constraint again
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_tournaments_share_token 
                    ON tournaments(share_token);
                """)
            
            conn.commit()
            print("Successfully added share_token column to tournaments table.")
            return True
        else:
            print("share_token column already exists.")
            return True
            
    except Exception as e:
        print(f"Error adding share_token column: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_share_token()
