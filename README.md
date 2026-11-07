# Gridiron Oracle

A local web app for weekly NFL picks. It rates teams with Elo plus home field, and shows your numerology and Chinese-zodiac readings beside each pick as a separate, adjustable signal.

## Install

You need **Python 3.9 or newer**. That's it: the app uses only Python's standard library, so there's nothing to `pip install`, and no Node build step.

```
cd gridiron-oracle
make test        # optional: run the test suite
```

No `make` (e.g. on Windows)? Every command has a plain-Python equivalent:

| make | plain Python |
|---|---|
| `make refresh` | `python3 -m oracle refresh` |
| `make run` | `python3 -m oracle run` |
| `make test` | `python3 -m oracle test` |

## Weekly routine

1. **`make refresh`** — downloads the latest nflverse `games.csv`, rebuilds every rating from the 2024 opener forward, grades finished games in the ledger, and saves picks for this week's unplayed games. It prints this week's picks and last week's record in the terminal.
2. **`make run`** — opens the app at http://127.0.0.1:8642. Leave it running while you browse; Ctrl+C stops it.

Refresh again any time (e.g. Tuesday after Monday night) to grade the week and roll forward. If the download fails, refresh keeps going with the last copy it saved.

## On your phone (GitHub Pages)

`.github/workflows/refresh.yml` runs the refresh on GitHub every morning at 10:00 UTC, commits the updated ledger and data back to the repo, and publishes `web/` plus `data/app.json` and `data/ledger.json` to GitHub Pages. Open the Pages link in Safari and choose Share → **Add to Home Screen**.

- Run it now: the repo's **Actions** tab → *Refresh and publish* → **Run workflow**.
- On the hosted copy, the Settings sliders are saved on that device only. To change the settings the ledger uses, edit `config/settings.json` in the repo.
- GitHub pauses scheduled workflows in repos with no activity for 60 days. The workflow's own data commits normally count as activity, but if it ever stops, re-enable it from the Actions tab.

## What's where

- **Slate** (home screen): the current week's games, Thursday through Monday. Each card shows kickoff, records, the pick and its probability, the model and market spreads (⚑ when they pick different sides) and the readings badge. Click a card for the full breakdown. Use ‹ › or the menus to move to any week from 2024 on.
- **Ledger**: picks saved each week and graded from real scores, with season-to-date hit rate overall, for 80%+ picks, and split by whether the readings agreed.
- **Backtest**: each season's record, hit rate and Brier score for always-home, readings only, strength + home, and strength + home + readings at your current settings, plus confidence buckets and the agree/disagree split.
- **Settings**: readings influence (default 0), astrology weight (25), numerology weight (75). The slate and backtest update instantly; the values are saved to `config/settings.json` and used for ledger picks at the next refresh.

Green is always the model's pick. Muted violet is always the readings.

## Editing team profiles

Profiles live in **`config/teams.json`**:

```json
"CHI": { "name": "Bears", "city": "Chicago", "born_day": 8, "life_path": 11, "pinnacle": 3, "animal": "Monkey" }
```

- Numbers must be 1–9, 11, 22 or 33. Animals must be one of Rat, Ox, Tiger, Cat, Dragon, Snake, Horse, Goat, Monkey, Rooster, Dog, Pig.
- When a team enters a new pinnacle, change `pinnacle`, save, and run `make refresh`. Refresh checks the file and tells you exactly what's wrong if a value is invalid.
- `aliases` maps abbreviations in the data file to these keys (`LA` → `LAR` for the Rams, plus older codes).

The readings rules themselves (reduction, relationships, weights) are in `oracle/readings.py`. They're implemented exactly as specified, and the tests in `tests/test_oracle.py` lock them in.

## How the pieces fit

- `oracle/elo.py` — rating math (start 1505, home field 30, K 25, margin-of-victory multiplier, one-third regression between seasons).
- `oracle/readings.py` — numerology, zodiac and team scoring.
- `oracle/model.py` — runs every game in date order (playoffs included) and attaches pre-game ratings, records and readings.
- `oracle/backtest.py`, `oracle/refresh.py` — backtest, ledger and the JSON the app reads (`data/app.json`, `data/ledger.json`).
- `oracle/server.py` + `web/` — a tiny local server and a plain HTML/JS front end.

**Why Python + plain HTML/JS:** no dependencies to install or update, one command to start, and the files are small enough to read. The model math is mirrored in `web/app.js` so sliders recompute picks and the backtest instantly without a rebuild.

## Notes on the ledger

The first refresh backfills earlier weeks of the current season, marked “backfilled”. Those picks use only results known before each kickoff (Elo is built game by game), but they weren't saved in advance, so the page labels them. Picks for unplayed games keep updating at each refresh until kickoff, then lock.

Neutral sites come from the data file's `location` column. The market spread is nflverse's `spread_line` (positive = home favored).

Picks don't account for injuries, quarterback changes or weather. For entertainment.
