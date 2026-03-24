from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Player, Tournament, Match, RatingHistory
from datetime import date, datetime
from collections import defaultdict
import json

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tennis.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "tennis-tracker-secret"
db.init_app(app)


def get_player():
    """Get the single player, or None if not set up yet."""
    return Player.query.first()


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if get_player():
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dob_str = request.form.get("dob", "").strip()
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None
        player = Player(name=name, dob=dob)
        db.session.add(player)
        db.session.commit()
        flash(f"Welcome, {name}! Start by adding a tournament.", "success")
        return redirect(url_for("index"))
    return render_template("setup.html")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    player = get_player()
    if not player:
        return redirect(url_for("setup"))

    tournaments = Tournament.query.order_by(Tournament.date.desc()).all()
    all_matches = Match.query.join(Tournament).order_by(Tournament.date).all()

    total_wins = sum(1 for m in all_matches if m.won)
    total_losses = sum(1 for m in all_matches if not m.won)
    total_matches = total_wins + total_losses
    win_pct = round(total_wins / total_matches * 100, 1) if total_matches else 0

    recent_tournaments = tournaments[:5]

    # Win rate by surface
    surface_stats = defaultdict(lambda: {"wins": 0, "losses": 0})
    for m in all_matches:
        surface = m.tournament.surface or "Unknown"
        if m.won:
            surface_stats[surface]["wins"] += 1
        else:
            surface_stats[surface]["losses"] += 1

    surface_data = []
    for surface, stats in surface_stats.items():
        total = stats["wins"] + stats["losses"]
        surface_data.append({
            "surface": surface,
            "wins": stats["wins"],
            "losses": stats["losses"],
            "win_pct": round(stats["wins"] / total * 100, 1) if total else 0,
        })

    return render_template(
        "index.html",
        player=player,
        tournaments=tournaments,
        recent_tournaments=recent_tournaments,
        total_wins=total_wins,
        total_losses=total_losses,
        total_matches=total_matches,
        win_pct=win_pct,
        surface_data=surface_data,
    )


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------

@app.route("/tournaments")
def tournaments():
    player = get_player()
    all_tournaments = Tournament.query.order_by(Tournament.date.desc()).all()
    return render_template("tournaments.html", player=player, tournaments=all_tournaments)


@app.route("/tournaments/add", methods=["GET", "POST"])
def add_tournament():
    player = get_player()
    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        t_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        draw_size = request.form.get("draw_size", "").strip()
        t = Tournament(
            name=request.form.get("name", "").strip(),
            date=t_date,
            location=request.form.get("location", "").strip() or None,
            surface=request.form.get("surface", "").strip() or None,
            level=request.form.get("level", "").strip() or None,
            draw_size=int(draw_size) if draw_size.isdigit() else None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(t)
        db.session.commit()
        flash("Tournament added!", "success")
        return redirect(url_for("tournament_detail", tid=t.id))
    return render_template("add_tournament.html", player=player)


@app.route("/tournaments/<int:tid>")
def tournament_detail(tid):
    player = get_player()
    t = Tournament.query.get_or_404(tid)
    return render_template("tournament_detail.html", player=player, tournament=t)


@app.route("/tournaments/<int:tid>/edit", methods=["GET", "POST"])
def edit_tournament(tid):
    player = get_player()
    t = Tournament.query.get_or_404(tid)
    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        t.date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else t.date
        t.name = request.form.get("name", "").strip()
        t.location = request.form.get("location", "").strip() or None
        t.surface = request.form.get("surface", "").strip() or None
        t.level = request.form.get("level", "").strip() or None
        draw_size = request.form.get("draw_size", "").strip()
        t.draw_size = int(draw_size) if draw_size.isdigit() else None
        t.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Tournament updated!", "success")
        return redirect(url_for("tournament_detail", tid=t.id))
    return render_template("add_tournament.html", player=player, tournament=t)


@app.route("/tournaments/<int:tid>/delete", methods=["POST"])
def delete_tournament(tid):
    t = Tournament.query.get_or_404(tid)
    Match.query.filter_by(tournament_id=tid).delete()
    db.session.delete(t)
    db.session.commit()
    flash("Tournament deleted.", "info")
    return redirect(url_for("tournaments"))


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

@app.route("/tournaments/<int:tid>/matches/add", methods=["GET", "POST"])
def add_match(tid):
    player = get_player()
    t = Tournament.query.get_or_404(tid)
    if request.method == "POST":
        won = request.form.get("won") == "true"
        opp_utr = request.form.get("opponent_utr", "").strip()
        aces = request.form.get("aces", "").strip()
        dfs = request.form.get("double_faults", "").strip()
        fsp = request.form.get("first_serve_pct", "").strip()
        winners = request.form.get("winners", "").strip()
        ue = request.form.get("unforced_errors", "").strip()

        m = Match(
            tournament_id=tid,
            round=request.form.get("round", "").strip() or None,
            opponent_name=request.form.get("opponent_name", "").strip(),
            opponent_utr=float(opp_utr) if opp_utr else None,
            score=request.form.get("score", "").strip() or None,
            won=won,
            aces=int(aces) if aces.isdigit() else None,
            double_faults=int(dfs) if dfs.isdigit() else None,
            first_serve_pct=float(fsp) if fsp else None,
            winners=int(winners) if winners.isdigit() else None,
            unforced_errors=int(ue) if ue.isdigit() else None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(m)
        db.session.commit()
        flash("Match logged!", "success")
        return redirect(url_for("tournament_detail", tid=tid))
    return render_template("add_match.html", player=player, tournament=t)


@app.route("/matches/<int:mid>/edit", methods=["GET", "POST"])
def edit_match(mid):
    player = get_player()
    m = Match.query.get_or_404(mid)
    if request.method == "POST":
        m.round = request.form.get("round", "").strip() or None
        m.opponent_name = request.form.get("opponent_name", "").strip()
        opp_utr = request.form.get("opponent_utr", "").strip()
        m.opponent_utr = float(opp_utr) if opp_utr else None
        m.score = request.form.get("score", "").strip() or None
        m.won = request.form.get("won") == "true"
        aces = request.form.get("aces", "").strip()
        dfs = request.form.get("double_faults", "").strip()
        fsp = request.form.get("first_serve_pct", "").strip()
        winners = request.form.get("winners", "").strip()
        ue = request.form.get("unforced_errors", "").strip()
        m.aces = int(aces) if aces.isdigit() else None
        m.double_faults = int(dfs) if dfs.isdigit() else None
        m.first_serve_pct = float(fsp) if fsp else None
        m.winners = int(winners) if winners.isdigit() else None
        m.unforced_errors = int(ue) if ue.isdigit() else None
        m.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Match updated!", "success")
        return redirect(url_for("tournament_detail", tid=m.tournament_id))
    return render_template("add_match.html", player=player, tournament=m.tournament, match=m)


@app.route("/matches/<int:mid>/delete", methods=["POST"])
def delete_match(mid):
    m = Match.query.get_or_404(mid)
    tid = m.tournament_id
    db.session.delete(m)
    db.session.commit()
    flash("Match deleted.", "info")
    return redirect(url_for("tournament_detail", tid=tid))


# ---------------------------------------------------------------------------
# Stats & Progress
# ---------------------------------------------------------------------------

@app.route("/stats")
def stats():
    player = get_player()
    all_matches = Match.query.join(Tournament).order_by(Tournament.date, Match.id).all()
    all_tournaments = Tournament.query.order_by(Tournament.date).all()
    rating_history = RatingHistory.query.filter_by(player_id=player.id).order_by(RatingHistory.date).all() if player else []

    # Cumulative win rate over time
    cumulative = []
    wins = 0
    total = 0
    for m in all_matches:
        total += 1
        if m.won:
            wins += 1
        cumulative.append({
            "date": m.tournament.date.strftime("%Y-%m-%d"),
            "win_pct": round(wins / total * 100, 1),
            "match_label": f"vs {m.opponent_name} ({m.tournament.name})",
        })

    # Win rate by tournament level
    level_stats = defaultdict(lambda: {"wins": 0, "losses": 0})
    for m in all_matches:
        level = m.tournament.level or "Other"
        if m.won:
            level_stats[level]["wins"] += 1
        else:
            level_stats[level]["losses"] += 1

    # Monthly win rate
    monthly = defaultdict(lambda: {"wins": 0, "total": 0})
    for m in all_matches:
        key = m.tournament.date.strftime("%Y-%m")
        monthly[key]["total"] += 1
        if m.won:
            monthly[key]["wins"] += 1
    monthly_data = sorted([
        {"month": k, "win_pct": round(v["wins"] / v["total"] * 100, 1), "total": v["total"]}
        for k, v in monthly.items()
    ], key=lambda x: x["month"])

    # Match stats averages
    def avg(values):
        vals = [v for v in values if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    stats_data = {
        "avg_aces": avg([m.aces for m in all_matches]),
        "avg_dfs": avg([m.double_faults for m in all_matches]),
        "avg_fsp": avg([m.first_serve_pct for m in all_matches]),
        "avg_winners": avg([m.winners for m in all_matches]),
        "avg_ue": avg([m.unforced_errors for m in all_matches]),
    }

    # UTR history
    utr_data = [
        {"date": r.date.strftime("%Y-%m-%d"), "utr": r.utr, "usta": r.usta_rating}
        for r in rating_history if r.utr is not None
    ]

    return render_template(
        "stats.html",
        player=player,
        all_matches=all_matches,
        all_tournaments=all_tournaments,
        cumulative=json.dumps(cumulative),
        level_stats=level_stats,
        monthly_data=json.dumps(monthly_data),
        stats_data=stats_data,
        utr_data=json.dumps(utr_data),
        rating_history=rating_history,
    )


# ---------------------------------------------------------------------------
# Opponents / Head-to-head
# ---------------------------------------------------------------------------

@app.route("/opponents")
def opponents():
    player = get_player()
    all_matches = Match.query.join(Tournament).order_by(Tournament.date, Match.id).all()

    opp_map = defaultdict(lambda: {"wins": 0, "losses": 0, "matches": []})
    for m in all_matches:
        key = m.opponent_name.strip()
        if m.won:
            opp_map[key]["wins"] += 1
        else:
            opp_map[key]["losses"] += 1
        opp_map[key]["matches"].append(m)

    opponents_list = []
    for name, data in opp_map.items():
        total = data["wins"] + data["losses"]
        opponents_list.append({
            "name": name,
            "wins": data["wins"],
            "losses": data["losses"],
            "total": total,
            "win_pct": round(data["wins"] / total * 100, 1) if total else 0,
            "matches": data["matches"],
        })
    opponents_list.sort(key=lambda x: x["total"], reverse=True)

    return render_template("opponents.html", player=player, opponents=opponents_list)


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

@app.route("/ratings/add", methods=["GET", "POST"])
def add_rating():
    player = get_player()
    if not player:
        return redirect(url_for("setup"))
    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        r_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        utr = request.form.get("utr", "").strip()
        ranking = request.form.get("usta_ranking", "").strip()
        r = RatingHistory(
            player_id=player.id,
            date=r_date,
            utr=float(utr) if utr else None,
            usta_rating=request.form.get("usta_rating", "").strip() or None,
            usta_ranking=int(ranking) if ranking.isdigit() else None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(r)
        db.session.commit()
        flash("Rating entry added!", "success")
        return redirect(url_for("stats"))
    return render_template("add_rating.html", player=player)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
