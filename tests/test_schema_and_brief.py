import unittest
from pathlib import Path

from notion_agent_os.brief import extract_open_todos, format_briefing
from notion_agent_os.schema import build_plan, load_schema

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestSchemaAndBrief(unittest.TestCase):
    def test_templates_valid_and_dry_run_plan(self):
        for tpl in ("student-life-os.json", "developer-os.json"):
            schema = load_schema(REPO_ROOT / "templates" / tpl)
            plan = build_plan(schema)
            self.assertGreater(len(plan), 5)
            self.assertTrue(plan[0].startswith("[HUB]"))

    def test_extract_open_todos_recursive(self):
        blocks = [
            {
                "type": "to_do",
                "to_do": {"checked": False, "rich_text": [{"plain_text": "Write docs"}]},
            },
            {
                "type": "to_do",
                "to_do": {"checked": True, "rich_text": [{"plain_text": "Completed"}]},
            },
            {
                "type": "toggle",
                "toggle": {"rich_text": [{"plain_text": "More"}]},
                "_children": [
                    {
                        "type": "to_do",
                        "to_do": {"checked": False, "rich_text": [{"plain_text": "Nested task"}]},
                    }
                ],
            },
        ]
        self.assertEqual(extract_open_todos(blocks), ["Write docs", "Nested task"])

    def test_format_briefing_compact(self):
        data = {
            "date": "2026-11-24",
            "window_days": 7,
            "events": [
                {"title": "Sprint Demo", "start": "2026-11-25", "end": "", "category": "Event", "location": "Online"}
            ],
            "tasks": {"Hub": ["Ship v0.1.0"]},
        }
        compact = format_briefing(data, compact=True)
        self.assertIn("BRIEF 2026-11-24 (+7d)", compact)
        self.assertIn("Sprint Demo @ Online", compact)
        self.assertIn("- [Hub] Ship v0.1.0", compact)


if __name__ == "__main__":
    unittest.main()
