-- Database schema for Chess Tournament Management System

-- Tournaments table
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    location TEXT,
    time_control TEXT,
    rounds INTEGER NOT NULL DEFAULT 5,
    current_round INTEGER DEFAULT 0,
    status TEXT DEFAULT 'upcoming', -- 'upcoming', 'ongoing', 'completed'
    created_by TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(username)
);

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    rating INTEGER,
    federation TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tournament Players (junction table)
CREATE TABLE IF NOT EXISTS tournament_players (
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    registration_number INTEGER,
    initial_rating INTEGER,
    current_score REAL DEFAULT 0.0,
    tiebreak1 REAL DEFAULT 0.0, -- Buchholz
    tiebreak2 REAL DEFAULT 0.0, -- Sonneborn-Berger
    tiebreak3 REAL DEFAULT 0.0, -- Direct encounter
    PRIMARY KEY (tournament_id, player_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

-- Rounds table
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    start_time TEXT,
    end_time TEXT,
    status TEXT DEFAULT 'pending', -- 'pending', 'in_progress', 'completed'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    UNIQUE(tournament_id, round_number)
);

-- Matches table
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    board_number INTEGER NOT NULL,
    white_player_id INTEGER,
    black_player_id INTEGER,
    result TEXT, -- '1-0', '0-1', '0.5-0.5', '+-', '-+', '='
    white_rating_change REAL,
    black_rating_change REAL,
    pgn TEXT,
    status TEXT DEFAULT 'scheduled', -- 'scheduled', 'in_progress', 'completed', 'bye', 'forfeit'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (white_player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (black_player_id) REFERENCES players(id) ON DELETE SET NULL
);

-- Player byes
CREATE TABLE IF NOT EXISTS player_byes (
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    points_awarded REAL DEFAULT 1.0,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tournament_id, player_id, round_number),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

-- User roles for tournaments
CREATE TABLE IF NOT EXISTS user_tournament_roles (
    username TEXT NOT NULL,
    tournament_id INTEGER NOT NULL,
    role TEXT NOT NULL, -- 'admin', 'arbiter', 'player'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (username, tournament_id, role),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_tournament_players_tournament ON tournament_players(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournament_players_player ON tournament_players(player_id);
CREATE INDEX IF NOT EXISTS idx_matches_tournament_round ON matches(tournament_id, round_id);
CREATE INDEX IF NOT EXISTS idx_rounds_tournament ON rounds(tournament_id);
CREATE INDEX IF NOT EXISTS idx_player_byes_tournament_player ON player_byes(tournament_id, player_id);
