"""Run the Elo history and attach readings to every game from 2024 on."""
import csv
import math

from . import elo
from .readings import game_numbers, score_team, readings_value, p_read
from .teams import canon

FIRST_SEASON = 2024


def _int(x):
    return int(float(x)) if x not in (None, "", "NA") else None


def _float(x):
    return float(x) if x not in (None, "", "NA") else None


def load_games(csv_path, aliases):
    games = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            season = _int(r["season"])
            if season is None or season < FIRST_SEASON:
                continue
            games.append({
                "id": r["game_id"],
                "season": season,
                "game_type": r["game_type"],
                "week": _int(r["week"]),
                "gameday": r["gameday"],
                "weekday": r.get("weekday", ""),
                "gametime": r.get("gametime", "") or "",
                "away": canon(r["away_team"], aliases),
                "home": canon(r["home_team"], aliases),
                "away_score": _int(r["away_score"]),
                "home_score": _int(r["home_score"]),
                "neutral": r.get("location", "") == "Neutral",
                "spread_line": _float(r.get("spread_line")),
                "stadium": r.get("stadium", ""),
            })
    games.sort(key=lambda g: (g["gameday"], g["gametime"], g["id"]))
    return games


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def logit(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def combine(p_elo, o_diff, influence):
    lam = (influence / 100.0) * 0.3
    return sigmoid(logit(p_elo) + lam * o_diff)


def run(games, teams, settings=None):
    """Annotate games in place with pre-game ratings, records and readings.

    Returns the final ratings dict.
    """
    settings = settings or {}
    w_astro = settings.get("w_astro", 25)
    w_num = settings.get("w_num", 75)
    ratings = {}
    records = {}
    season = None
    for g in games:
        if g["season"] != season:
            if season is not None:
                ratings = {t: elo.regress(r) for t, r in ratings.items()}
            season = g["season"]
            records = {}
        for t in (g["home"], g["away"]):
            if t not in teams:
                raise KeyError("Team %r is not in config/teams.json (add it, or an alias)" % t)
            ratings.setdefault(t, elo.START)
            records.setdefault(t, [0, 0, 0])
        rh, ra = ratings[g["home"]], ratings[g["away"]]
        d = elo.diff(rh, ra, g["neutral"])
        g["elo_home"], g["elo_away"] = round(rh, 2), round(ra, 2)
        g["diff"] = d
        g["p_elo"] = elo.p_home(d)
        g["est_spread"] = elo.spread(d)
        g["rec_home"] = "-".join(map(str, records[g["home"]][:2] + ([records[g["home"]][2]] if records[g["home"]][2] else [])))
        g["rec_away"] = "-".join(map(str, records[g["away"]][:2] + ([records[g["away"]][2]] if records[g["away"]][2] else [])))

        gn = game_numbers(g["gameday"])
        g["gnums"] = gn
        sh = score_team(teams[g["home"]], gn)
        sa = score_team(teams[g["away"]], gn)
        g["read_home"], g["read_away"] = sh, sa
        g["o_diff"] = readings_value(sh["num"], sh["astro"], w_astro, w_num) - readings_value(sa["num"], sa["astro"], w_astro, w_num)
        g["p_read"] = p_read(g["o_diff"])

        if g["home_score"] is not None and g["away_score"] is not None:
            delta, _, _ = elo.update(rh, ra, g["home_score"], g["away_score"], g["neutral"])
            ratings[g["home"]] = rh + delta
            ratings[g["away"]] = ra - delta
            g["elo_delta"] = delta
            hs, as_ = g["home_score"], g["away_score"]
            if hs > as_:
                records[g["home"]][0] += 1; records[g["away"]][1] += 1
            elif hs < as_:
                records[g["home"]][1] += 1; records[g["away"]][0] += 1
            else:
                records[g["home"]][2] += 1; records[g["away"]][2] += 1
    return ratings


def o_diff_for(g, w_astro, w_num):
    return (readings_value(g["read_home"]["num"], g["read_home"]["astro"], w_astro, w_num)
            - readings_value(g["read_away"]["num"], g["read_away"]["astro"], w_astro, w_num))


def pick(g, settings):
    """Return (pick_team, p_home_combined, confidence, o_diff) for given settings."""
    od = o_diff_for(g, settings.get("w_astro", 25), settings.get("w_num", 75))
    ph = combine(g["p_elo"], od, settings.get("influence", 0))
    team = g["home"] if ph >= 0.5 else g["away"]
    return team, ph, max(ph, 1 - ph), od


def readings_badge(g, pick_team, od):
    if abs(od) < 1e-9:
        return "even", None
    fav = g["home"] if od > 0 else g["away"]
    return ("agree", fav) if fav == pick_team else ("favor", fav)
