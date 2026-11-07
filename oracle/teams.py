"""Load and validate the editable team profiles in config/teams.json."""
import json
import os

from .readings import ANIMALS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_FILE = os.path.join(ROOT, "config", "teams.json")
VALID_NUMS = set(range(1, 10)) | {11, 22, 33}


def load_teams(path=TEAMS_FILE):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    teams = raw["teams"]
    aliases = raw.get("aliases", {})
    problems = []
    for abbr, t in teams.items():
        for k in ("born_day", "life_path", "pinnacle"):
            if t.get(k) not in VALID_NUMS:
                problems.append("%s %s=%r (must be 1-9, 11, 22 or 33)" % (abbr, k, t.get(k)))
        if t.get("animal") not in ANIMALS:
            problems.append("%s animal=%r (must be one of %s)" % (abbr, t.get("animal"), ", ".join(ANIMALS)))
    if problems:
        raise ValueError("config/teams.json has problems:\n  " + "\n  ".join(problems))
    return teams, aliases


def canon(abbr, aliases):
    return aliases.get(abbr, abbr)
