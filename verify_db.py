import os
import sqlite3

def verify_database():
    db_path = 'tournament.db'
    
    # Check if file exists and has content
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        print("Database file is empty or doesn't exist!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print("No tables found in the database!")
            return
            
        print("Tables in the database:")
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            
            # Get table info
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                if not columns:
                    print("  No columns found!")
                    continue
                    
                print("  Columns:")
                for col in columns:
                    print(f"    {col[1]} ({col[2]})")
                    
            except sqlite3.Error as e:
                print(f"  Error reading table info: {e}")
                
    except Exception as e:
        print(f"Error accessing database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    verify_database()
