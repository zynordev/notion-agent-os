import unittest

from notion_agent_os.markdown import (
    blocks_to_markdown,
    markdown_to_blocks,
    markdown_to_rich_text,
    rich_text_to_markdown,
)


class TestMarkdownEngine(unittest.TestCase):
    def test_inline_formatting_roundtrip(self):
        src = "Hello **bold**, *italic*, `code`, ~~old~~, and [Notion](https://notion.so)."
        rt = markdown_to_rich_text(src)
        # Simulate Notion API's plain_text field
        for seg in rt:
            seg["plain_text"] = seg["text"]["content"]
        rendered = rich_text_to_markdown(rt)
        self.assertEqual(rendered, src)

    def test_blocks_conversion(self):
        md = """# Title
## Section
- [ ] Unchecked task
- [x] Done task
- Bullet item
1. Numbered item
> A quote
---
```py
print("hello")
```
| Col A | Col B |
| --- | --- |
| 1 | 2 |
"""
        blocks = markdown_to_blocks(md)
        types = [b["type"] for b in blocks]
        self.assertEqual(
            types,
            [
                "heading_1",
                "heading_2",
                "to_do",
                "to_do",
                "bulleted_list_item",
                "numbered_list_item",
                "quote",
                "divider",
                "code",
                "table",
            ],
        )
        self.assertFalse(blocks[2]["to_do"]["checked"])
        self.assertTrue(blocks[3]["to_do"]["checked"])
        self.assertEqual(blocks[8]["code"]["language"], "python")
        self.assertEqual(blocks[9]["table"]["table_width"], 2)

    def test_blocks_to_markdown_compact_and_nested(self):
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {"rich_text": [{"plain_text": "Hub"}]},
            },
            {
                "type": "to_do",
                "to_do": {
                    "checked": False,
                    "rich_text": [{"plain_text": "Parent task"}],
                },
                "_children": [
                    {
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"plain_text": "Nested detail"}]
                        },
                    }
                ],
            },
            {
                "type": "divider",
                "divider": {},
            },
            {
                "id": "page-123",
                "type": "child_page",
                "child_page": {"title": "Notes"},
            },
        ]
        md = blocks_to_markdown(blocks, compact=True)
        self.assertIn("# Hub", md)
        self.assertIn("- [ ] Parent task", md)
        self.assertIn("  - Nested detail", md)
        self.assertNotIn("---", md)
        self.assertIn("[PAGE] Notes (page-123)", md)


if __name__ == "__main__":
    unittest.main()
