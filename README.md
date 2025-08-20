# 🏆 Chess Tournament Pairings System

A comprehensive Swiss-system tournament management application built with Python, Flask, and SQLite. This system handles player registration, round management, pairings, and results tracking for chess tournaments.

## ✨ Features

- **Tournament Management**: Create and manage multiple tournaments
- **Player Management**: Add and track players with ratings
- **Swiss System Pairings**: Automatic pairings based on the Swiss system
- **Results Tracking**: Record game results and update standings
- **Tiebreaks**: Built-in tiebreak calculations (Buchholz, etc.)
- **Responsive UI**: Works on desktop and mobile devices
- **User Authentication**: Secure login system for tournament organizers

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ChessPairings.git
   cd ChessPairings
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python -c "from app import init_db; init_db()"
   ```

### Running the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 🎮 Usage

### Creating a Tournament

1. Click on "New Tournament"
2. Enter tournament details (name, number of rounds, dates)
3. Add players to the tournament
4. Click "Start Tournament" to generate the first round pairings

### Managing Rounds

1. After each round, record the game results
2. Click "Generate Next Round" to create pairings for the next round
3. Continue until all rounds are completed

### Viewing Results

- **Standings**: See current rankings with tiebreaks
- **Pairings**: View all pairings by round
- **Player Stats**: Track individual player performance

## 🛠️ Technical Details

### Database Schema

The application uses SQLite with the following main tables:
- `users`: User accounts and authentication
- `tournaments`: Tournament information
- `players`: Player information
- `rounds`: Tournament rounds
- `pairings`: Individual game pairings and results

### Pairing Algorithm

The system implements a Swiss-system pairing algorithm that:
1. Groups players by score
2. Sorts within groups by rating
3. Avoids rematches
4. Balances color assignments
5. Handles byes for odd numbers of players

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)
- Icons from [Font Awesome](https://fontawesome.com/)

Swiss System for Chess — Summary
🧠 Purpose
A Swiss-system tournament pairs players with similar scores each round, allowing many players to compete fairly and efficiently over a few rounds — without elimination.

🏁 How It Works
📌 Core Principles
All players play every round.

Players are paired with opponents on equal or similar scores.

No one plays the same opponent twice.

Effort is made to alternate colors (white/black) each round.

Number of rounds is fixed before the event (usually log₂(n) + 1).

📋 Before the Tournament
Collect all player names, ratings (if using), and optionally seed the list.

Decide:

Number of rounds (e.g., 5 for 20–30 players).

Tiebreak systems (see below).

Time control (e.g., 10+5 or 90+30).

Ruleset (FIDE, CFC, etc.).

Determine how you'll record results (paper forms, spreadsheet, software).

🔁 Each Round
1. Group by Score
Players are grouped into "score brackets" based on total points so far.

2. Sort Within Each Group
Sort by:

Total score

Then by rating (optional)

Then alphabetically or at random

3. Pair Players
Pair top vs bottom (or nearest) in each group.

Avoid repeat opponents.

Attempt to alternate colors from previous rounds.

4. Assign Byes (if odd number)
One player gets a full-point bye.

Only assign to a player once, ideally to the lowest-ranked eligible.

⚖️ Scoring
Win = 1 point

Draw = 0.5 points

Loss = 0 points

Bye = 1 point (or 0.5 if half-point byes allowed)

⚙️ Color Assignment
Try to alternate colors for each player (W-B-W… or B-W-B…).

If perfect alternation isn’t possible:

Avoid more than two of the same color in a row.

Prefer players who have had fewer whites/blacks so far.

🧮 Tiebreak Systems
Use these only at the end if players are tied in points:

System	Purpose
Buchholz	Sum of opponents' scores.
Median Buchholz	Buchholz, but remove top/bottom opponent score.
Sonneborn-Berger	Score of defeated opponents + ½ of drawn ones.
Head-to-Head	Result of direct match between tied players.
Most Wins	Total number of wins.

Also add options for 
- Single elimination
- Double elimination
- Round robin