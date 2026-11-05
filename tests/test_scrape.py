import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
import scrape  # noqa: E402

CFG = json.loads((ROOT / "tests" / "fixture_config.json").read_text())
J = scrape.make_job


def fixtures():
    recent = scrape.NOW.date().isoformat()
    return [
        ("a", lambda: [
            J("remotive", "HRIS Administrator", "Acme", "https://x/1", "USA Only", recent, "", "ADP and UKG, async friendly, fully remote", True),
            J("remotive", "HRIS Administrator", "Acme", "https://x/1b", "USA Only", recent, "", "duplicate by title and company", True),
            J("remotive", "Director of People", "Acme", "https://x/2", "USA", recent, "", "x", True),
            J("remotive", "Recruiter", "EuroCo", "https://x/3", "Europe", recent, "", "x", True),
            J("remotive", "Leave Specialist", "Michco", "https://x/4", "Michigan", recent, "", "FMLA, on-call rotation and 24/7 coverage", True),
            J("remotive", "Leave Specialist", "PaCo", "https://x/5", "Pennsylvania", recent, "", "FMLA", True),
            J("remotive", "Senior Recruiter", "Old", "https://x/6", "USA", "2020-01-01", "", "x", True),
            J("greenhouse:foo", "HR Generalist", "OnsiteCo", "https://x/7", "Chicago, IL", recent, "", "x", False),
            J("greenhouse:foo", "HR Generalist", "RemoteCo", "https://x/8", "Remote - US", recent, "", "x", False),
            J("remotive", "Software Engineer", "Acme", "https://x/9", "USA", recent, "", "x", True),
            J("remotive", "International Recruiter", "Intl", "https://x/10", "USA", recent, "", "x", True),
        ]),
        ("b", lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
    ]


class T(unittest.TestCase):
    def setUp(self):
        self.res, self.new = scrape.build(CFG, {"jobs": []}, fixtures())
        self.by = {j["url"]: j for j in self.res["jobs"]}

    def test_kept_and_dropped(self):
        self.assertEqual(set(self.by), {"https://x/1", "https://x/4", "https://x/5", "https://x/8", "https://x/10"})

    def test_restricted_flag(self):
        self.assertTrue(self.by["https://x/4"]["restricted"])
        self.assertFalse(self.by["https://x/5"]["restricted"])

    def test_scoring(self):
        self.assertGreater(self.by["https://x/1"]["score"], 60)
        self.assertLess(self.by["https://x/4"]["score"], 50)
        self.assertIn("24/7", self.by["https://x/4"]["flags"])

    def test_failed_source_keeps_old_jobs(self):
        old = self.res
        res2, _ = scrape.build(CFG, old, [("a", lambda: []), ("remotive", lambda: (_ for _ in ()).throw(RuntimeError("down")))])
        # source "a" succeeded but returned nothing; jobs came from source "remotive" which failed, so they are kept
        self.assertTrue(any(j["url"] == "https://x/1" for j in res2["jobs"]))
        self.assertTrue(res2["failed_sources"])

    def test_first_seen_preserved(self):
        old = {"jobs": [dict(self.by["https://x/1"], first_seen="2026-01-01")]}
        res2, new = scrape.build(CFG, old, fixtures())
        self.assertEqual({j["url"]: j for j in res2["jobs"]}["https://x/1"]["first_seen"], "2026-01-01")
        self.assertNotIn(self.by["https://x/1"]["id"], new)


if __name__ == "__main__":
    unittest.main()
