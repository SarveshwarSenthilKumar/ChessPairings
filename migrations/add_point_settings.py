import sqlite3

def add_point_settings_columns(db_path='tournament.db'):
    """Add point settings columns to the tournaments table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add new columns with default values
        cursor.execute('''
        ALTER TABLE tournaments 
        ADD COLUMN win_points REAL DEFAULT 1.0
        ''')
        
        cursor.execute('''
        ALTER TABLE tournaments 
        ADD COLUMN draw_points REAL DEFAULT 0.5
        ''')
        
        cursor.execute('''
        ALTER TABLE tournaments 
        ADD COLUMN loss_points REAL DEFAULT 0.0
        ''')
        
        cursor.execute('''
        ALTER TABLE tournaments 
        ADD COLUMN bye_points REAL DEFAULT 1.0
        ''')
        
        conn.commit()
        print("Successfully added point settings columns to tournaments table.")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Point settings columns already exist.")
        else:
            print(f"Error adding point settings columns: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_point_settings_columns()
