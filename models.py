from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = "player"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    rating_history = db.relationship("RatingHistory", backref="player", lazy=True, order_by="RatingHistory.date")

    @property
    def latest_rating(self):
        if self.rating_history:
            return self.rating_history[-1]
        return None


class Tournament(db.Model):
    __tablename__ = "tournament"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200), nullable=True)
    surface = db.Column(db.String(50), nullable=True)   # Hard, Clay, Grass, Indoor Hard
    level = db.Column(db.String(100), nullable=True)    # USTA L1-L5, UTR, etc.
    draw_size = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    matches = db.relationship("Match", backref="tournament", lazy=True, order_by="Match.id")

    @property
    def wins(self):
        return sum(1 for m in self.matches if m.won)

    @property
    def losses(self):
        return sum(1 for m in self.matches if not m.won)

    @property
    def best_round(self):
        round_order = [
            "Final", "Semifinal", "Quarterfinal",
            "Round of 16", "Round of 32", "Round of 64",
            "Round Robin", "Consolation Final", "Consolation Semifinal",
            "Round 1", "Round 2", "Round 3"
        ]
        for r in round_order:
            for m in self.matches:
                if m.round and r.lower() in m.round.lower():
                    return m.round
        if self.matches:
            return self.matches[-1].round
        return None


class Match(db.Model):
    __tablename__ = "match"
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), nullable=False)
    round = db.Column(db.String(50), nullable=True)
    opponent_name = db.Column(db.String(100), nullable=False)
    opponent_utr = db.Column(db.Float, nullable=True)
    score = db.Column(db.String(100), nullable=True)   # e.g. "6-3 6-4" or "4-6 7-5 6-3"
    won = db.Column(db.Boolean, nullable=False, default=False)
    # Match stats
    aces = db.Column(db.Integer, nullable=True)
    double_faults = db.Column(db.Integer, nullable=True)
    first_serve_pct = db.Column(db.Float, nullable=True)   # 0-100
    winners = db.Column(db.Integer, nullable=True)
    unforced_errors = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    @property
    def sets(self):
        """Parse score into list of (player_games, opponent_games) tuples."""
        if not self.score:
            return []
        sets = []
        for s in self.score.strip().split():
            if "-" in s:
                parts = s.split("-")
                try:
                    p = int(parts[0])
                    o = int(parts[1].split("(")[0])  # strip tiebreak notation
                    sets.append((p, o))
                except (ValueError, IndexError):
                    pass
        return sets


class RatingHistory(db.Model):
    __tablename__ = "rating_history"
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    utr = db.Column(db.Float, nullable=True)
    usta_rating = db.Column(db.String(20), nullable=True)   # e.g. "10U", "12U", "4.0"
    usta_ranking = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
