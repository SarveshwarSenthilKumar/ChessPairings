-- Create tournaments table with all required columns
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    rounds INTEGER DEFAULT 5,
    time_control TEXT,
    status TEXT DEFAULT 'upcoming',
    created_at TEXT NOT NULL,
    creator_id INTEGER NOT NULL,
    description TEXT,
    prize_winners INTEGER DEFAULT 0
);

-- Verify the table was created
SELECT name FROM sqlite_master WHERE type='table';

-- Show the table structure
PRAGMA table_info(tournaments);
