"""Backtest the four strategies on completed games. Ties are excluded."""
from . import elo
from .model import combine, o_diff_for
from .readings import p_read

BUCKETS = [(0.5, 0.6, "50–59"), (0.6, 0.7, "60–69"), (0.7, 0.8, "70–79"), (0.8, 1.01, "80+")]
P_HOME_ONLY = elo.p_home(elo.HFA)  # what equal ratings + home field implies


def _stat():
    return {"w": 0, "l": 0, "brier": 0.0}


def _add(s, p_home, home_won):
    picked_home = p_home >= 0.5
    if picked_home == home_won:
        s["w"] += 1
    else:
        s["l"] += 1
    s["brier"] += (p_home - (1.0 if home_won else 0.0)) ** 2


def _fin(s):
    n = s["w"] + s["l"]
    return {"w": s["w"], "l": s["l"], "n": n,
            "hit": s["w"] / n if n else None,
            "brier": s["brier"] / n if n else None}


def season_backtest(games, season, settings):
    wa, wn, inf = settings.get("w_astro", 25), settings.get("w_num", 75), settings.get("influence", 0)
    strat = {k: _stat() for k in ("home", "readings", "strength", "combined")}
    buckets = {b[2]: _stat() for b in BUCKETS}
    agree = {"agree": _stat(), "disagree": _stat(), "even": _stat()}
    for g in games:
        if g["season"] != season or g["home_score"] is None or g["home_score"] == g["away_score"]:
            continue
        hw = g["home_score"] > g["away_score"]
        od = o_diff_for(g, wa, wn)
        pr = p_read(od)
        pc = combine(g["p_elo"], od, inf)
        # Always-home: picks home every time; Brier uses the home-field-only probability.
        s = strat["home"]
        s["w" if hw else "l"] += 1
        s["brier"] += ((0.5 if g["neutral"] else P_HOME_ONLY) - (1.0 if hw else 0.0)) ** 2
        _add(strat["readings"], pr, hw)
        _add(strat["strength"], g["p_elo"], hw)
        _add(strat["combined"], pc, hw)
        conf = max(pc, 1 - pc)
        for lo, hi, name in BUCKETS:
            if lo <= conf < hi:
                _add(buckets[name], pc, hw)
        strength_home = g["p_elo"] >= 0.5
        if abs(od) < 1e-9:
            key = "even"
        else:
            key = "agree" if (od > 0) == strength_home else "disagree"
        _add(agree[key], g["p_elo"], hw)
    return {"season": season,
            "strategies": {k: _fin(v) for k, v in strat.items()},
            "buckets": {k: _fin(v) for k, v in buckets.items()},
            "agreement": {k: _fin(v) for k, v in agree.items()}}


def backtest(games, settings):
    seasons = sorted({g["season"] for g in games if g["home_score"] is not None})
    return [season_backtest(games, s, settings) for s in seasons]
