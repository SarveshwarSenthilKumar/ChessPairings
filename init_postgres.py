import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

def get_db_connection():
    """Create and return a connection to the PostgreSQL database."""
    load_dotenv()  # Load environment variables from .env file
    
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME', 'chess_tournament'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432')
        )
        conn.autocommit = True
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        raise

def create_database():
    """Create the database if it doesn't exist."""
    try:
        # Connect to the default 'postgres' database to create a new database
        conn = psycopg2.connect(
            dbname='postgres',
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432')
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        db_name = os.getenv('DB_NAME', 'chess_tournament')
        cursor.execute(sql.SQL("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s"), [db_name])
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"Database '{db_name}' created successfully.")
        else:
            print(f"Database '{db_name}' already exists.")
            
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Error creating database: {e}")
        raise

def create_tables():
    """Create all necessary tables in the PostgreSQL database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enable UUID extension
        cursor.execute("CREATE EXTENSION IF NOT EXISTS "uuid-ossp";")
        
        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            last_login TIMESTAMP WITH TIME ZONE,
            email VARCHAR(255) UNIQUE,
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE
        )''')
        
        # Tournaments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            location VARCHAR(255),
            start_date TIMESTAMP WITH TIME ZONE NOT NULL,
            end_date TIMESTAMP WITH TIME ZONE NOT NULL,
            rounds INTEGER NOT NULL DEFAULT 5,
            time_control VARCHAR(50),
            status VARCHAR(20) NOT NULL DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'in_progress', 'completed')),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            description TEXT,
            prize_winners INTEGER NOT NULL DEFAULT 0,
            share_token UUID UNIQUE,
            win_points NUMERIC(5,2) NOT NULL DEFAULT 1.0,
            draw_points NUMERIC(5,2) NOT NULL DEFAULT 0.5,
            loss_points NUMERIC(5,2) NOT NULL DEFAULT 0.0,
            bye_points NUMERIC(5,2) NOT NULL DEFAULT 1.0,
            comments TEXT DEFAULT ''
        )''')
        
        # Players table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            rating INTEGER NOT NULL DEFAULT 1200,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            team VARCHAR(100),
            fide_id VARCHAR(20),
            title VARCHAR(10),
            federation CHAR(3),
            is_active BOOLEAN DEFAULT TRUE
        )''')
        
        # Tournament Players table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_players (
            tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            initial_rating INTEGER NOT NULL,
            score NUMERIC(10,2) NOT NULL DEFAULT 0.0,
            tiebreak1 NUMERIC(10,2) NOT NULL DEFAULT 0.0,
            tiebreak2 NUMERIC(10,2) NOT NULL DEFAULT 0.0,
            tiebreak3 NUMERIC(10,2) NOT NULL DEFAULT 0.0,
            requested_bye_round INTEGER,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tournament_id, player_id)
        )''')
        
        # Rounds table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL,
            start_time TIMESTAMP WITH TIME ZONE,
            end_time TIMESTAMP WITH TIME ZONE,
            status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE (tournament_id, round_number)
        )''')
        
        # Pairings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pairings (
            id SERIAL PRIMARY KEY,
            round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
            white_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            black_player_id INTEGER REFERENCES players(id) ON DELETE SET NULL,
            board_number INTEGER NOT NULL,
            result VARCHAR(10) CHECK (result IN ('1-0', '0-1', '0.5-0.5', '0-0', '1-0F', '0-1F', NULL)),
            status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'bye')),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT different_players CHECK (white_player_id != black_player_id)
        )''')
        
        # Manual Byes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS manual_byes (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE (tournament_id, player_id, round_number)
        )''')
        
        # Admin Share Links table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_share_links (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            token UUID NOT NULL UNIQUE,
            permissions JSONB NOT NULL,
            created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE,
            max_uses INTEGER,
            use_count INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_used_at TIMESTAMP WITH TIME ZONE
        )''')
        
        # Create indexes
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournament_players_player 
        ON tournament_players(player_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament 
        ON tournament_players(tournament_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_rounds_tournament 
        ON rounds(tournament_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pairings_round 
        ON pairings(round_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_manual_byes_player 
        ON manual_byes(player_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_manual_byes_tournament 
        ON manual_byes(tournament_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_admin_share_links_token 
        ON admin_share_links(token)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_tournaments_share_token 
        ON tournaments(share_token)
        ''')
        
        # Create function to update updated_at timestamp
        cursor.execute('''
        CREATE OR REPLACE FUNCTION update_modified_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        ''')
        
        # Create triggers for updated_at
        for table in ['tournament_players', 'rounds', 'pairings', 'manual_byes']:
            cursor.execute(f'''
            DROP TRIGGER IF EXISTS update_{table}_modtime ON {table};
            CREATE TRIGGER update_{table}_modtime
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_modified_column();
            ''')
        
        conn.commit()
        print("Database tables created successfully.")
        
    except Exception as e:
        print(f"Error creating tables: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cursor.close()
            conn.close()

def main():
    """Main function to set up the database and tables."""
    try:
        print("Setting up PostgreSQL database...")
        create_database()
        create_tables()
        print("Database setup completed successfully!")
    except Exception as e:
        print(f"Failed to set up database: {e}")
        return 1
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
