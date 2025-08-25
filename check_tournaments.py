import sqlite3

def check_tournaments_table():
    try:
        conn = sqlite3.connect('tournament.db')
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(tournaments)")
        columns = cursor.fetchall()
        
        if not columns:
            print("The 'tournaments' table does not exist or has no columns.")
            return
            
        print("Columns in 'tournaments' table:")
        for col in columns:
            print(f"- {col[1]} ({col[2]})")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_tournaments_table()
