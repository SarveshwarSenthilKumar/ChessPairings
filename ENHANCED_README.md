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

## 🚀 Getting Started
1. Clone this repository
2. Configure your tournament settings
3. Add player information
4. Run the pairing system

## 📝 License
This project is open source and available for anyone to use for tournament pairings.

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
