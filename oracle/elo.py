"""Strength rating (Elo) with home field and margin-of-victory multiplier."""
import math

START = 1505.0
HFA = 30.0
K = 25.0
POINTS_PER_SPREAD = 25.0


def regress(r):
    return r * (2.0 / 3.0) + START * (1.0 / 3.0)


def diff(r_home, r_away, neutral):
    return r_home + (0.0 if neutral else HFA) - r_away


def p_home(d):
    return 1.0 / (1.0 + 10 ** (-d / 400.0))


def update(r_home, r_away, home_pts, away_pts, neutral):
    """Return (delta, pElo, diff). Apply as R_home += delta, R_away -= delta."""
    d = diff(r_home, r_away, neutral)
    p = p_home(d)
    if home_pts > away_pts:
        result, winner_diff = 1.0, d
    elif home_pts < away_pts:
        result, winner_diff = 0.0, -d
    else:
        result, winner_diff = 0.5, 0.0
    mov = abs(home_pts - away_pts)
    mult = math.log(max(mov, 1) + 1) * 2.2 / (winner_diff * 0.001 + 2.2)
    delta = K * mult * (result - p)
    return delta, p, d


def spread(d):
    """Estimated spread in points, positive = home favored."""
    return d / POINTS_PER_SPREAD
