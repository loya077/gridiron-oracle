"""Numerology and Chinese-zodiac readings, implemented exactly as specified.

Nothing in this file should change without the owner's sign-off: these are
the owner's rules, not tunable model parameters.
"""
import math
from datetime import date

MASTERS = (11, 22, 33)

# ---------------------------------------------------------------- reduction

def _digit_sum(n):
    return sum(int(c) for c in str(abs(int(n))))


def reduce(n):
    """Reduce a total to 1-9, keeping master numbers.

    * 11 is kept at any stage; 20 counts as 11 at any stage.
    * 22 and 33 are kept only when the starting total is exactly 22 or 33.
    """
    n = int(n)
    if n in (22, 33):
        return n
    while True:
        if n == 11:
            return 11
        if n == 20:
            return 11
        if 1 <= n <= 9:
            return n
        if n == 0:
            return 0
        n = _digit_sum(n)


# ---------------------------------------------------------------- game date

LUNAR_NEW_YEAR = {
    2024: date(2024, 2, 10),
    2025: date(2025, 1, 29),
    2026: date(2026, 2, 17),
    2027: date(2027, 2, 6),
    2028: date(2028, 1, 26),
    2029: date(2029, 2, 13),
    2030: date(2030, 2, 3),
}

ANIMALS = ["Rat", "Ox", "Tiger", "Cat", "Dragon", "Snake",
           "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]


def _as_date(d):
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def day_number(d):
    return reduce(_as_date(d).day)


def life_path(d):
    d = _as_date(d)
    digits = "%02d%02d%04d" % (d.month, d.day, d.year)
    return reduce(sum(int(c) for c in digits))


def lunar_year(d):
    d = _as_date(d)
    if d.year not in LUNAR_NEW_YEAR:
        raise ValueError("No Lunar New Year date on file for %d; add it to LUNAR_NEW_YEAR" % d.year)
    return d.year if d >= LUNAR_NEW_YEAR[d.year] else d.year - 1


def year_animal(d):
    return ANIMALS[(lunar_year(d) - 2020) % 12]


def game_numbers(d):
    return {"day": day_number(d), "life_path": life_path(d), "animal": year_animal(d)}


# ---------------------------------------------------------------- relationships

NUM_ENEMIES = [{1, 9}, {2, 9}, {3, 4}, {4, 5}, {5, 6}, {7, 8}, {9, 11}, {9, 22}]
NUM_GROUPS = [{1, 4, 7}, {2, 5, 8}, {3, 6, 9}]


def num_rel(a, b):
    """Return (points, label) for two numbers."""
    pair = {a, b}
    if a != b and pair in NUM_ENEMIES:
        return -3, "Enemies"
    if pair == {7, 11}:
        return 4, "Soulmates"
    if a == b:
        return 3, "Match"
    if a in MASTERS or b in MASTERS:
        return 2, "Master"
    for g in NUM_GROUPS:
        if a in g and b in g:
            return 2, "Friendly"
    return 0, "Neutral"


def numRel(a, b):  # name used in the spec
    return num_rel(a, b)[0]


ANIMAL_ENEMIES = [{"Rat", "Horse"}, {"Ox", "Goat"}, {"Tiger", "Monkey"},
                  {"Cat", "Rooster"}, {"Dragon", "Dog"}, {"Snake", "Pig"}]
ANIMAL_TRINES = [{"Rat", "Dragon", "Monkey"}, {"Ox", "Snake", "Rooster"},
                 {"Tiger", "Horse", "Dog"}, {"Cat", "Goat", "Pig"}]


def animal_rel(a, b):
    """Return (points, label) for team animal vs. year animal."""
    if a == b:
        return 0, "Same"
    pair = {a, b}
    if pair == {"Rat", "Ox"}:
        return 4, "Soulmates"
    if pair in ANIMAL_ENEMIES:
        return -3, "Enemies"
    for t in ANIMAL_TRINES:
        if pair <= t:
            return 3, "Trine"
    return 0, "Neutral"


# ---------------------------------------------------------------- team score

WEIGHTS = (("born_day", "Born day", 1), ("life_path", "Life path", 2), ("pinnacle", "Pinnacle", 3))
NUM_MAX = 4 * 2 * (3 + 2 + 1)  # 48
AST_MAX = 4


def score_team(profile, gnums):
    """Score one team for one game date. Returns num, astro and a factor list."""
    factors = []
    num = 0
    for key, label, w in WEIGHTS:
        tn = profile[key]
        for gkey, glabel in (("life_path", "game life path"), ("day", "game day")):
            pts, rel = num_rel(tn, gnums[gkey])
            num += pts * w
            factors.append({"factor": label, "team": tn, "vs": glabel, "game": gnums[gkey],
                            "rel": rel, "points": pts, "weight": w, "weighted": pts * w})
    apts, arel = animal_rel(profile["animal"], gnums["animal"])
    return {"num": num, "astro": apts, "astro_rel": arel, "factors": factors}


def readings_value(num, astro, w_astro=25, w_num=75):
    return (w_astro / 10.0) * (astro / float(AST_MAX)) + (w_num / 10.0) * (num / float(NUM_MAX)) * 2


def p_read(o_diff):
    return 1.0 / (1.0 + math.exp(-o_diff / 2.5))
