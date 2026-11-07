"""Weekly refresh: download data, rebuild ratings, save and grade picks, export JSON."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from datetime import date, datetime, timedelta, timezone

from .teams import ROOT, load_teams
from .model import load_games, run, pick, readings_badge
from .backtest import backtest

DATA_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
DATA_DIR = os.path.join(ROOT, "data")
CSV_PATH = os.path.join(DATA_DIR, "games.csv")
APP_JSON = os.path.join(DATA_DIR, "app.json")
LEDGER = os.path.join(DATA_DIR, "ledger.json")
SETTINGS = os.path.join(ROOT, "config", "settings.json")
DEFAULT_SETTINGS = {"influence": 0, "w_astro": 25, "w_num": 75}


# ---------------------------------------------------------------- helpers

def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s.update(json.load(f))
    except FileNotFoundError:
        pass
    return s


def save_settings(s):
    clean = {k: max(0, min(100, int(round(float(s.get(k, DEFAULT_SETTINGS[k])))))) for k in DEFAULT_SETTINGS}
    _write_json(SETTINGS, clean)
    return clean


def _write_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"))
        else:
            json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def download(url=DATA_URL, dest=CSV_PATH):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gridiron-oracle/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    if not body.startswith(b"game_id,"):
        raise ValueError("Downloaded file doesn't look like the nflverse games.csv")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)


def _eastern_offset(d):
    """UTC offset for US Eastern time on date d (DST: 2nd Sun Mar - 1st Sun Nov)."""
    def nth_sunday(y, m, n):
        first = date(y, m, 1)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    dst = nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)
    return timedelta(hours=-4 if dst else -5)


def kickoff_utc(g):
    d = date.fromisoformat(g["gameday"])
    hh, mm = (g["gametime"] or "13:00").split(":")[:2]
    local = datetime(d.year, d.month, d.day, int(hh), int(mm))
    return (local - _eastern_offset(d)).replace(tzinfo=timezone.utc)


def current_week(games, today):
    """Season and week to show by default: the first week with an unplayed game
    on or after today; otherwise the latest week in the data."""
    for g in games:
        if g["home_score"] is None and g["gameday"] >= (today - timedelta(days=3)).isoformat():
            return g["season"], g["week"]
    last = games[-1]
    return last["season"], last["week"]


# ---------------------------------------------------------------- ledger

def _entry(g, settings, source, now):
    team, ph, conf, od = pick(g, settings)
    kind, fav = readings_badge(g, team, od)
    return {
        "id": g["id"], "season": g["season"], "week": g["week"], "gameday": g["gameday"],
        "away": g["away"], "home": g["home"], "pick": team,
        "p_home": round(ph, 4), "conf": round(conf, 4), "p_elo": round(g["p_elo"], 4),
        "o_diff": round(od, 4), "readings": kind, "readings_fav": fav,
        "est_spread": round(g["est_spread"], 2), "market_spread": g["spread_line"],
        "settings": dict(settings), "source": source, "saved_at": now.isoformat(timespec="seconds"),
    }


def _grade(e, g):
    if g["home_score"] == g["away_score"]:
        e["outcome"] = "tie"
    else:
        winner = g["home"] if g["home_score"] > g["away_score"] else g["away"]
        e["outcome"] = "win" if e["pick"] == winner else "loss"
    e["score"] = "%s %d, %s %d" % (g["away"], g["away_score"], g["home"], g["home_score"])


def update_ledger(games, settings, cur, now):
    try:
        with open(LEDGER, encoding="utf-8") as f:
            ledger = json.load(f)
    except FileNotFoundError:
        ledger = {"picks": {}}
    picks = ledger["picks"]
    season, week = cur
    saved = graded = backfilled = 0
    for g in games:
        if g["season"] != season or g["week"] > week:
            continue
        e = picks.get(g["id"])
        scored = g["home_score"] is not None
        if scored:
            if e is None:
                # Missed week (or first run): record the pick the model would have
                # made before kickoff. Elo only uses earlier games, so no hindsight.
                e = picks[g["id"]] = _entry(g, settings, "backfill", now)
                backfilled += 1
            if "outcome" not in e:
                _grade(e, g)
                graded += 1
        else:
            started = kickoff_utc(g) <= now
            if e is None or (not started and e.get("source") == "live"):
                picks[g["id"]] = _entry(g, settings, "live" if not started else "late", now)
                saved += 1
    ledger["updated_at"] = now.isoformat(timespec="seconds")
    _write_json(LEDGER, ledger)
    return ledger, saved, graded, backfilled


# ---------------------------------------------------------------- export

def export(games, teams, ratings, settings, cur, now):
    out_games = []
    for g in games:
        out_games.append({
            "id": g["id"], "season": g["season"], "week": g["week"], "type": g["game_type"],
            "gameday": g["gameday"], "weekday": g["weekday"], "gametime": g["gametime"],
            "away": g["away"], "home": g["home"],
            "away_score": g["away_score"], "home_score": g["home_score"],
            "neutral": g["neutral"], "stadium": g["stadium"], "spread_line": g["spread_line"],
            "elo_home": g["elo_home"], "elo_away": g["elo_away"],
            "p_elo": round(g["p_elo"], 5), "diff": round(g["diff"], 2),
            "rec_home": g["rec_home"], "rec_away": g["rec_away"],
            "gnums": g["gnums"], "read_home": g["read_home"], "read_away": g["read_away"],
        })
    weeks = {}
    for g in games:
        weeks.setdefault(str(g["season"]), set()).add(g["week"])
    app = {
        "generated_at": now.isoformat(timespec="seconds"),
        "current": {"season": cur[0], "week": cur[1]},
        "weeks": {s: sorted(w) for s, w in weeks.items()},
        "settings": settings,
        "teams": teams,
        "ratings": {t: round(r, 1) for t, r in sorted(ratings.items(), key=lambda kv: -kv[1])},
        "games": out_games,
    }
    _write_json(APP_JSON, app, compact=True)


# ---------------------------------------------------------------- main

def fmt_pct(x):
    return "—" if x is None else "%.1f%%" % (100 * x)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Refresh Gridiron Oracle data, ratings and ledger")
    ap.add_argument("--offline", action="store_true", help="skip the download and use data/games.csv")
    ap.add_argument("--csv", help="use this games.csv instead of downloading")
    ap.add_argument("--today", help="pretend today is YYYY-MM-DD (for testing)")
    args = ap.parse_args(argv)

    if args.csv:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.abspath(args.csv) != os.path.abspath(CSV_PATH):
            shutil.copyfile(args.csv, CSV_PATH)
    elif not args.offline:
        try:
            print("Downloading nflverse games.csv …")
            download()
        except Exception as e:  # keep working from the cached copy
            if not os.path.exists(CSV_PATH):
                sys.exit("Download failed (%s) and there is no cached data/games.csv." % e)
            print("  Download failed (%s); using the cached copy." % e)

    now = datetime.now(timezone.utc)
    today = date.fromisoformat(args.today) if args.today else datetime.now().date()
    if args.today:
        now = datetime(today.year, today.month, today.day, 20, 0, tzinfo=timezone.utc)

    teams, aliases = load_teams()
    settings = load_settings()
    games = load_games(CSV_PATH, aliases)
    ratings = run(games, teams, settings)
    cur = current_week(games, today)
    ledger, saved, graded, backfilled = update_ledger(games, settings, cur, now)
    export(games, teams, ratings, settings, cur, now)

    print("Ratings rebuilt from %d games (%d played)." % (len(games), sum(g["home_score"] is not None for g in games)))
    print("Ledger: %d picks saved/updated, %d graded%s." % (
        saved, graded, (", %d backfilled" % backfilled) if backfilled else ""))
    # last week's grades
    lw = [e for e in ledger["picks"].values() if e["season"] == cur[0] and e["week"] == cur[1] - 1 and e.get("outcome") in ("win", "loss")]
    if lw:
        w = sum(e["outcome"] == "win" for e in lw)
        print("Week %d results: %d-%d" % (cur[1] - 1, w, len(lw) - w))
    for s in backtest(games, settings):
        st = s["strategies"]["strength"]
        print("Backtest %d strength+home: %d-%d (%s), Brier %.4f" % (s["season"], st["w"], st["l"], fmt_pct(st["hit"]), st["brier"]))
    print("\nWeek %d, %d season (settings: influence %d, astro %d, numerology %d)" % (
        cur[1], cur[0], settings["influence"], settings["w_astro"], settings["w_num"]))
    for g in games:
        if g["season"] == cur[0] and g["week"] == cur[1]:
            team, ph, conf, od = pick(g, settings)
            kind, fav = readings_badge(g, team, od)
            badge = {"agree": "Readings agree", "even": "Readings even"}.get(kind, "Readings favor %s" % fav)
            done = "  final %s %s-%s %s" % (g["away"], g["away_score"], g["home_score"], g["home"]) if g["home_score"] is not None else ""
            print("  %s %-5s %3s @ %-3s  pick %-3s %5.1f%%  %s%s" % (
                g["gameday"][5:], g["gametime"], g["away"], g["home"], team, 100 * conf, badge, done))
    print("\nWrote data/app.json and data/ledger.json. Start the app with: make run")


if __name__ == "__main__":
    main()
