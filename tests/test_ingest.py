import unittest

from notion_agent_os.ingest import format_git_digest_markdown, parse_ics


SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Robotics Championship
DTSTART:20261201T090000Z
DTEND:20261201T173000Z
LOCATION:Innovation Hall\\, Main Campus
DESCRIPTION:Line one\\nLine two
  continuation
END:VEVENT
BEGIN:VEVENT
SUMMARY:All Day Exam
DTSTART;VALUE=DATE:20261210
END:VEVENT
END:VCALENDAR
"""


class TestIngest(unittest.TestCase):
    def test_parse_ics_unfolding_and_dates(self):
        events = parse_ics(SAMPLE_ICS, default_category="Academic")
        self.assertEqual(len(events), 2)

        ev1 = events[0]
        self.assertEqual(ev1.summary, "Robotics Championship")
        self.assertEqual(ev1.start, "2026-12-01T09:00:00Z")
        self.assertEqual(ev1.end, "2026-12-01T17:30:00Z")
        self.assertEqual(ev1.location, "Innovation Hall, Main Campus")
        self.assertIn("Line one\nLine two continuation", ev1.description)
        self.assertEqual(ev1.category, "Academic")

        ev2 = events[1]
        self.assertEqual(ev2.summary, "All Day Exam")
        self.assertEqual(ev2.start, "2026-12-10")
        self.assertIsNone(ev2.end)

    def test_format_git_digest(self):
        commits = [
            {"hash": "abc1234", "date": "2026-11-24", "author": "dev", "subject": "feat: add CLI"},
        ]
        md = format_git_digest_markdown("sample-repo", commits, date_label="2026-11-24")
        self.assertIn("### Git Activity — sample-repo (2026-11-24)", md)
        self.assertIn("- `abc1234` feat: add CLI (2026-11-24)", md)


if __name__ == "__main__":
    unittest.main()
