# 🏆 Chess Tournament Pairing System

A comprehensive Swiss-system tournament pairing solution for chess clubs and events. Originally created for Zugzwang Chess Club, this system can be used by anyone for tournament pairings.

## 🎯 Purpose
A Swiss-system tournament pairs players with similar scores each round, allowing many players to compete fairly and efficiently over a few rounds — without elimination.

## ✨ Features
- **Swiss System Pairings**
- Multiple tiebreak systems
- Color assignment balancing
- Support for byes
- Flexible tournament formats:
  - Swiss (primary focus)
  - Single elimination
  - Double elimination
  - Round robin

## 🏁 How It Works

### 📌 Core Principles
- All players compete in every round
- Players face opponents with similar scores
- No repeated pairings
- Color alternation (white/black) each round
- Fixed number of rounds (typically log₂(n) + 1)

## 🛠️ Tournament Setup

### 📋 Before the Tournament
1. **Player Registration**
   - Collect player names
   - Include ratings (if available)
   - Optionally seed players

2. **Tournament Configuration**
   - Determine number of rounds (e.g., 5 for 20–30 players)
   - Select time control (e.g., 10+5 or 90+30)
   - Choose ruleset (FIDE, CFC, etc.)
   - Select tiebreak systems (see below)
   - Decide on result recording method (paper, spreadsheet, software)

## 🔄 Round Management

### 1. Grouping by Score
Players are grouped into "score brackets" based on their current tournament points.

### 2. Sorting Within Groups
Players within each group are sorted by:
1. Total score (highest first)
2. Rating (if available)
3. Alphabetical order or random (as tiebreaker)

### 3. Player Pairing
- Pair top vs bottom within each score group
- Prevent repeated pairings
- Balance color assignments from previous rounds

### 4. Bye Assignment (if odd number of players)
- One player receives a full-point bye
- Each player should receive at most one bye
- Byes are typically given to the lowest-ranked eligible player

## 📊 Scoring System
- **Win**: 1 point
- **Draw**: 0.5 points
- **Loss**: 0 points
- **Bye**: 1 point (configurable to 0.5 points if half-point byes are allowed)

## ⚙️ Color Assignment Rules
- Alternate colors (W-B-W… or B-W-B…) when possible
- If perfect alternation isn't possible:
  - Avoid more than two of the same color in a row
  - Prioritize players who have had fewer whites/blacks

## 🏆 Tiebreak Systems
When players are tied on points, the following tiebreak systems are available:

| System | Description |
|--------|-------------|
| **Buchholz** | Sum of all opponents' scores |
| **Median Buchholz** | Buchholz, but removes highest and lowest opponent scores |
| **Sonneborn-Berger** | Sum of defeated opponents' scores + ½ of drawn opponents' scores |
| **Head-to-Head** | Result of direct encounter between tied players |
| **Most Wins** | Total number of wins in the tournament |

# 🏆 Chess Tournament Pairings - User Manual

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Modern web browser

### Installation
1. Clone this repository
   ```bash
   git clone [your-repository-url]
   cd Zugzwang-Chess-Pairings/ChessPairings
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   # OR
   source venv/bin/activate  # On macOS/Linux
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python init_db.py
   ```

5. Run the application:
   ```bash
   flask run
   ```

6. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## 📋 User Guide

### 1. Tournament Creation
1. Click on "Create New Tournament"
2. Fill in the tournament details:
   - Tournament Name
   - Location
   - Start/End Dates
   - Number of Rounds
   - Time Control
   - Description (optional)
3. Click "Create Tournament"

### 2. Managing Players
#### Adding Players
1. Navigate to your tournament
2. Click on "Manage Players"
3. To add a new player:
   - Enter player details (Name, Rating, Team)
   - Click "Add Player"
4. To import multiple players:
   - Prepare a CSV/Excel file with columns: name, rating
   - Click "Import Players"
   - Select your file and upload

#### Removing Players
1. In the "Current Players" section
2. Click the trash icon next to the player you want to remove
3. Confirm the removal

### 3. Adjusting Player Points
1. Go to "Manage Players"
2. In the "Current Players" table, find the player
3. In the "Add Points" column:
   - Enter the number of points to add (use negative to subtract)
   - Click the "+" button to apply

### 4. Generating Pairings
1. Navigate to "Manage Pairings"
2. Select the round number
3. Choose pairing method:
   - Swiss System (default)
   - Round Robin
   - Manual Pairing
4. Click "Generate Pairings"

### 5. Entering Results
1. In the pairings view, find the match
2. Click on the result field
3. Select the outcome:
   - 1-0 (White wins)
   - 0-1 (Black wins)
   - ½-½ (Draw)
   - 0-0 (Double Forfeit)
4. Click "Save"

### 6. Viewing Standings
1. Go to "Standings"
2. View the current rankings
3. Sort by different criteria using the column headers

### 7. Tournament Completion
1. After the final round, go to "Tournament Settings"
2. Click "Conclude Tournament"
3. View final standings and download results

## 🔧 Troubleshooting

### Common Issues
- **Application won't start**:
  - Ensure all dependencies are installed
  - Check if the database file exists and has proper permissions
  - Look for error messages in the console

- **Database issues**:
  - Try running `python init_db.py` to reset the database
  - Make sure the database file is not open in another program

- **JSON encoding errors**:
  - Make sure all date objects are properly serialized
  - Check for any None values that should be converted to empty strings

## 📞 Support
For additional help, please contact [your-email@example.com] or open an issue in the repository.

## 📝 License

## 📝 License
This project is open source and available for anyone to use for tournament pairings.

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
