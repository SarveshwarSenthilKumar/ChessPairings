# Chess Tournament Management System

A comprehensive web application for managing chess tournaments using the Swiss system, built with Python Flask and SQLite.

## 🚀 Features

- **Tournament Management**: Create and manage multiple tournaments
- **Player Management**: Add, edit, and remove players
- **Swiss System Pairings**: Automatic pairing based on player scores
- **Round Management**: Track rounds and match results
- **Standings & Tiebreaks**: Real-time standings with multiple tiebreak systems
- **User Authentication**: Secure login system with different user roles
- **Responsive Design**: Works on desktop and mobile devices

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ChessPairings.git
   cd ChessPairings
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the database**
   ```bash
   python createDatabase.py
   ```

5. **Configure environment variables**
   Create a `.env` file in the project root with the following:
   ```
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key-here
   ```

6. **Run the application**
   ```bash
   flask run
   ```
   The application will be available at `http://localhost:5000`

## 🔑 Default Admin Account

- **Username**: admin
- **Password**: admin123 (change this after first login)

## 📚 Technical Stack

- **Backend**: Python 3.9+, Flask
- **Database**: SQLite (with SQLAlchemy ORM)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Authentication**: Flask-Login with password hashing
- **Templates**: Jinja2

## 📋 Database Schema

The application uses the following main tables:

- **users**: User accounts and authentication
- **tournaments**: Tournament information
- **players**: Player profiles
- **tournament_players**: Junction table for tournament participants
- **rounds**: Tournament rounds
- **matches**: Individual chess matches
- **user_tournament_roles**: User permissions for tournaments

## 🧩 API Endpoints

- `GET /` - Home page
- `GET /tournaments` - List all tournaments
- `GET /tournaments/<int:tournament_id>` - View tournament details
- `GET /tournaments/create` - Create new tournament form
- `POST /tournaments/create` - Create new tournament
- `POST /tournaments/<int:tournament_id>/update` - Update tournament
- `GET /auth/login` - Login page
- `POST /auth/login` - Process login
- `GET /auth/signup` - Signup page
- `POST /auth/signup` - Process signup
- `GET /auth/logout` - Logout

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Contact

For any questions or feedback, please open an issue on GitHub.

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