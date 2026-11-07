import math
import os
import unittest

from oracle.readings import reduce, game_numbers, numRel, animal_rel, score_team
from oracle import elo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "data", "games.csv")


class TestReduce(unittest.TestCase):
    def test_reduce(self):
        self.assertEqual(reduce(20), 11)
        self.assertEqual(reduce(29), 11)
        self.assertEqual(reduce(22), 22)
        self.assertEqual(reduce(31), 4)
        self.assertEqual(reduce(12), 3)
        self.assertEqual(reduce(33), 33)
        self.assertEqual(reduce(38), 11)
        self.assertEqual(reduce(47), 11)


class TestGameDate(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(game_numbers("2026-11-08"), {"day": 8, "life_path": 11, "animal": "Horse"})
        self.assertEqual(game_numbers("2026-11-09"), {"day": 9, "life_path": 3, "animal": "Horse"})
        self.assertEqual(game_numbers("2027-01-10")["animal"], "Horse")
        self.assertEqual(game_numbers("2025-12-07")["animal"], "Snake")

    def test_day_examples(self):
        self.assertEqual(game_numbers("2026-11-12")["day"], 3)
        self.assertEqual(game_numbers("2026-11-20")["day"], 11)
        self.assertEqual(game_numbers("2026-11-29")["day"], 11)

    def test_lunar_boundary(self):
        self.assertEqual(game_numbers("2026-02-16")["animal"], "Snake")
        self.assertEqual(game_numbers("2026-02-17")["animal"], "Horse")
        self.assertEqual(game_numbers("2025-01-28")["animal"], "Dragon")


class TestRelations(unittest.TestCase):
    def test_num(self):
        self.assertEqual(numRel(9, 11), -3)
        self.assertEqual(numRel(33, 9), 2)
        self.assertEqual(numRel(7, 11), 4)
        self.assertEqual(numRel(1, 7), 2)
        self.assertEqual(numRel(7, 8), -3)
        self.assertEqual(numRel(11, 11), 3)
        self.assertEqual(numRel(9, 22), -3)
        self.assertEqual(numRel(1, 2), 0)

    def test_animals(self):
        self.assertEqual(animal_rel("Rat", "Horse")[0], -3)
        self.assertEqual(animal_rel("Tiger", "Horse")[0], 3)
        self.assertEqual(animal_rel("Cat", "Pig")[0], 3)
        self.assertEqual(animal_rel("Rat", "Ox")[0], 4)
        self.assertEqual(animal_rel("Horse", "Horse")[0], 0)

    def test_score_max(self):
        perfect = {"born_day": 7, "life_path": 7, "pinnacle": 7, "animal": "Rat"}
        s = score_team(perfect, {"day": 11, "life_path": 11, "animal": "Ox"})
        self.assertEqual(s["num"], 48)
        self.assertEqual(s["astro"], 4)


class TestElo(unittest.TestCase):
    def test_single_game(self):
        delta, p, d = elo.update(1505, 1505, 24, 17, neutral=False)
        # by hand: diff=30, pElo=1/(1+10^(-30/400)), mov=7
        p_hand = 1 / (1 + 10 ** (-30 / 400))
        mult = math.log(8) * 2.2 / (30 * 0.001 + 2.2)
        self.assertAlmostEqual(d, 30.0)
        self.assertAlmostEqual(p, p_hand)
        self.assertAlmostEqual(p, 0.543066, places=5)
        self.assertAlmostEqual(delta, 25 * mult * (1 - p_hand))
        self.assertAlmostEqual(delta, 23.4346, places=3)

    def test_neutral_and_spread(self):
        self.assertEqual(elo.diff(1505, 1505, True), 0)
        self.assertEqual(elo.spread(50), 2.0)


@unittest.skipUnless(os.path.exists(CSV), "run a refresh first to download data/games.csv")
class TestBacktest(unittest.TestCase):
    def test_2025_strength(self):
        from oracle.teams import load_teams
        from oracle.model import load_games, run
        from oracle.backtest import season_backtest
        teams, aliases = load_teams()
        games = load_games(CSV, aliases)
        run(games, teams)
        s = season_backtest(games, 2025, {"influence": 0})["strategies"]["strength"]
        self.assertLessEqual(abs(s["w"] - 182), 4, s)
        self.assertLessEqual(abs(s["l"] - 102), 4, s)


if __name__ == "__main__":
    unittest.main()
