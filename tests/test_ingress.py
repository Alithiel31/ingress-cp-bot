import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ingress as ig
from commands import ALL_COMMANDS, ENTRIES, fmt_countdown, handle_command, menu_commands

PARIS = ZoneInfo("Europe/Paris")


def ts(y, m, d, h=0, mi=0, tz=timezone.utc):
    return int(datetime(y, m, d, h, mi, tzinfo=tz).timestamp())


class LogicTests(unittest.TestCase):
    def test_reference_epoch_is_a_cycle_start(self):
        # Premier cycle des scores régionaux : 2014-01-15 10:00 UTC (commentaire du plugin IITC)
        self.assertEqual(ts(2014, 1, 15, 10) % ig.CYCLE_S, 0)

    def test_35_checkpoints_per_cycle(self):
        start = ig.cycle_start_of(ts(2026, 10, 10, 13))
        cps = ig.checkpoints_between(start + 1, start + ig.CYCLE_S + 1)
        self.assertEqual(len(cps), 35)
        self.assertEqual(cps[-1], start + ig.CYCLE_S)  # le dernier = fin du cycle

    def test_next_checkpoint_is_strictly_after_and_aligned(self):
        now = ts(2026, 10, 10, 13, 3)
        nxt = ig.next_checkpoint(now)
        self.assertGreater(nxt, now)
        self.assertLessEqual(nxt - now, ig.CHECKPOINT_S)
        self.assertEqual(nxt % ig.CHECKPOINT_S, 0)
        # exactement sur un checkpoint -> le suivant
        self.assertEqual(ig.next_checkpoint(nxt), nxt + ig.CHECKPOINT_S)

    def test_day_has_4_or_5_checkpoints_even_on_dst_days(self):
        for d in (date(2026, 10, 10), date(2026, 10, 25), date(2026, 3, 29)):  # 25 h / 23 h
            self.assertIn(len(ig.checkpoints_of_day(d, PARIS)), (4, 5), d)

    def test_days_partition_the_checkpoints(self):
        # 10 jours consécutifs : aucun checkpoint perdu ni compté deux fois
        total = sum(len(ig.checkpoints_of_day(date(2026, 10, 20 + i), PARIS)) for i in range(10))
        a, _ = ig.day_bounds(date(2026, 10, 20), PARIS)
        _, b = ig.day_bounds(date(2026, 10, 29), PARIS)
        self.assertEqual(total, len(ig.checkpoints_between(a, b)))

    def test_hour_filter(self):
        now = ts(2026, 10, 10, 13)
        res = ig.next_checkpoints_at_hour(14, now, 5, PARIS)
        self.assertEqual(len(res), 5)
        self.assertTrue(all(ig.local(t, PARIS).hour == 14 for t in res))
        self.assertEqual(res, sorted(res))

    def test_cycle_labels_are_consecutive_and_roundtrip(self):
        cycles = ig.cycles_of_year(2026, PARIS)
        # 365 j / 7,29 j ≈ 50,06 septicycles par an
        self.assertIn(len(cycles), (50, 51))
        self.assertEqual([c[0] for c in cycles], list(range(1, len(cycles) + 1)))
        for n, start, end in cycles:
            self.assertEqual(end - start, ig.CYCLE_S)
            self.assertEqual(ig.cycle_label(start, PARIS), f"2026.{n:02d}")
        self.assertEqual(ig.cycle_of_year(2026, 1, PARIS)[1], cycles[0][1])
        self.assertIsNone(ig.cycle_of_year(2026, 99, PARIS))

    def test_first_cycle_of_year_starts_in_the_first_175h(self):
        for year in (2025, 2026, 2027):
            first = ig.cycles_of_year(year, PARIS)[0][1]
            jan1 = int(datetime(year, 1, 1, tzinfo=PARIS).timestamp())
            self.assertGreaterEqual(first, jan1)
            self.assertLess(first - jan1, ig.CYCLE_S)


class CommandTests(unittest.TestCase):
    NOW = ts(2026, 10, 10, 13, 3)

    def run_cmd(self, cmd, arg=""):
        return handle_command(cmd, arg, self.NOW, PARIS)

    def test_all_commands_answer(self):
        for cmd, arg in [
            ("help", ""), ("tos", ""), ("today", ""), ("tomorrow", ""), ("next", ""),
            ("cp", ""), ("cp", "2026-12-25"), ("cp", "14H"), ("cp", "9"),
            ("cycle", ""), ("sp", ""), ("septicycle", ""), ("sp", "2026.05"), ("sp", "2026"),
        ]:
            out = self.run_cmd(cmd, arg)
            self.assertTrue(out and isinstance(out, str), (cmd, arg))

    def test_bad_arguments_are_reported(self):
        self.assertIn("invalide", self.run_cmd("cp", "2026-02-30"))
        self.assertIn("invalide", self.run_cmd("cp", "25h"))
        self.assertIn("n'existe pas", self.run_cmd("sp", "2026.99"))
        self.assertIn("non reconnu", self.run_cmd("sp", "abc"))
        self.assertIsNone(self.run_cmd("nope"))

    def test_year_listing_fits_in_one_telegram_message(self):
        self.assertLess(len(self.run_cmd("sp", "2026")), 4096)

    def test_help_and_tos_are_in_french(self):
        self.assertIn("Prochain checkpoint", self.run_cmd("help"))
        self.assertIn("Conditions d'utilisation", self.run_cmd("tos"))

    def test_countdown_never_shows_zero_minutes(self):
        self.assertEqual(fmt_countdown(1000, 1000), "dans moins d'une minute")
        self.assertEqual(fmt_countdown(1000 + 90 * 60, 1000), "dans 1 h 30 min")

    def test_help_lists_every_registered_command(self):
        text = self.run_cmd("help")
        for e in ENTRIES:
            self.assertIn(e.usage, text)
            self.assertIn(e.command, ALL_COMMANDS)

    def test_help_marks_restricted_commands_only_when_auth_is_on(self):
        self.assertNotIn("🔒", self.run_cmd("help"))
        locked = handle_command("help", "", self.NOW, PARIS, auth_enabled=True)
        self.assertIn("🔒 /today", locked)
        self.assertIn("🔒 /sp yyyy", locked)
        self.assertNotIn("🔒 /help", locked)
        self.assertNotIn("🔒 /tos", locked)

    def test_telegram_menu_matches_the_bot(self):
        menu = menu_commands()
        self.assertTrue(menu)
        for cmd, desc in menu:
            self.assertRegex(cmd, r"^[a-z0-9_]{1,32}$")
            self.assertTrue(1 <= len(desc) <= 256)
            self.assertIn(cmd, ALL_COMMANDS)
            self.assertIsNotNone(self.run_cmd(cmd))
        self.assertEqual(len({cmd for cmd, _ in menu}), len(menu))


if __name__ == "__main__":
    unittest.main()
