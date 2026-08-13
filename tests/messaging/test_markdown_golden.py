"""Golden characterization tests for markdown rendering.

These tests pin the exact byte output of both Telegram MarkdownV2 and Discord
markdown converters before the Sprint 6 refactor (extraction of the shared
inline token-walk skeleton). They must pass BEFORE extraction and remain
byte-identical AFTER extraction.

If any golden output changes during refactor, the abstraction is wrong and
must be revised or reverted.
"""

import pytest

from claudey.messaging.rendering.discord_markdown import render_markdown_to_discord
from claudey.messaging.rendering.telegram_markdown import render_markdown_to_mdv2


@pytest.mark.parametrize(
    "markdown,expected_telegram,expected_discord",
    [
        # Empty
        ("", "", ""),
        # Plain text
        ("hello world", "hello world", "hello world"),
        # Headings
        (
            "# Heading 1\n## Heading 2",
            "*Heading 1*\n*Heading 2*",
            "**Heading 1**\n**Heading 2**",
        ),
        # Bold, italic, strikethrough
        (
            "**bold** *italic* ~~strike~~",
            "*bold* _italic_ ~strike~",
            "**bold** *italic* ~~strike~~",
        ),
        # Nested emphasis
        ("***nested***", "_*nested*_", "***nested***"),
        # Inline code with escaping
        ("use `a\\b` here", "use `a\\\\b` here", "use `a\\\\b` here"),
        # Fenced code block with escaping
        (
            "```python\nprint(`x`)\\path\n```",
            "```\nprint(\\`x\\`)\\\\path\n```",
            "```\nprint(\\`x\\`)\\\\path\n```",
        ),
        # Link (Telegram escapes closing paren in URL)
        (
            "[text](https://example.com/a_(b))",
            "[text](https://example.com/a_(b\\))",
            "[text](https://example.com/a_(b))",
        ),
        # Link with inline code in text
        (
            "[text `code`](https://example.com)",
            "[text code](https://example.com)",
            "[text code](https://example.com)",
        ),
        # Image with alt text containing markdown
        (
            "![alt *text*](https://img.example/a.png)",
            "alt \\*text\\* (https://img.example/a.png)",
            "alt \\*text\\* (https://img.example/a.png)",
        ),
        # Image without alt text
        (
            "![](https://img.example/b.png)",
            "https://img.example/b.png",
            "https://img.example/b.png",
        ),
        # Bullet list (Telegram escapes dash)
        ("- first\n- second", "\\- first\n\n\\- second", "- first\n\n- second"),
        # Ordered list (Telegram escapes period)
        (
            "3. third\n4. fourth",
            "3\\. third\n\n4\\. fourth",
            "3. third\n\n4. fourth",
        ),
        # Blockquote
        (
            "> quoted *text*\n> next",
            "> quoted _text_\n> next",
            "> quoted *text*\n> next",
        ),
        # HTML entities (Telegram escapes special chars)
        (
            "AT&amp;T &lt;tag&gt; &#35;1",
            "AT&T <tag\\> \\#1",
            "AT&T <tag\\> #1",
        ),
        # Table (both render as code block)
        (
            "| A | B |\n|---|---|\n| 1 | `two` |",
            "```\n| A   | B   |\n| --- | --- |\n| 1   | two |\n```",
            "```\n| A   | B   |\n| --- | --- |\n| 1   | two |\n```",
        ),
        # Line breaks (soft/hard breaks become \n)
        ("first  \nsecond\nthird", "first\nsecond\nthird", "first\nsecond\nthird"),
        # Multi-paragraph
        ("Para one.\n\nPara two.", "Para one\\.\nPara two\\.", "Para one.\nPara two."),
        # Mixed structures
        (
            "# Title\n\n**bold** and *italic* and `code`.\n\n- item1\n- item2\n\n> quote\n\n[link](https://example.com)",
            "*Title*\n*bold* and _italic_ and `code`\\.\n\\- item1\n\n\\- item2\n\n\n> quote\n\n[link](https://example.com)",
            "**Title**\n**bold** and *italic* and `code`.\n- item1\n\n- item2\n\n\n> quote\n\n[link](https://example.com)",
        ),
    ],
    ids=[
        "empty",
        "plain_text",
        "headings",
        "emphasis",
        "nested_emphasis",
        "inline_code_escape",
        "fenced_code_escape",
        "link_url_escape",
        "link_inline_code",
        "image_alt_markdown",
        "image_no_alt",
        "bullet_list",
        "ordered_list",
        "blockquote",
        "html_entities",
        "table",
        "line_breaks",
        "multi_paragraph",
        "mixed",
    ],
)
def test_markdown_rendering_byte_identical(
    markdown: str, expected_telegram: str, expected_discord: str
):
    """Both converters produce exact expected byte output (pre-refactor golden)."""
    telegram_out = render_markdown_to_mdv2(markdown)
    discord_out = render_markdown_to_discord(markdown)

    assert telegram_out == expected_telegram, (
        f"Telegram output changed.\n"
        f"Expected: {expected_telegram!r}\n"
        f"Got:      {telegram_out!r}"
    )
    assert discord_out == expected_discord, (
        f"Discord output changed.\n"
        f"Expected: {expected_discord!r}\n"
        f"Got:      {discord_out!r}"
    )


def test_nested_list_structure():
    """Nested lists render with correct structure (both platforms)."""
    markdown = "- a\n  - b\n- c"
    telegram_out = render_markdown_to_mdv2(markdown)
    discord_out = render_markdown_to_discord(markdown)

    assert telegram_out == "\\- a\n\\- b\n\n\n\n\\- c"
    assert discord_out == "- a\n- b\n\n\n\n- c"


def test_table_with_multiple_rows():
    """Table with header and multiple data rows."""
    markdown = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    telegram_out = render_markdown_to_mdv2(markdown)
    discord_out = render_markdown_to_discord(markdown)

    expected_table = (
        "```\n| A   | B   |\n| --- | --- |\n| 1   | 2   |\n| 3   | 4   |\n```"
    )
    assert telegram_out == expected_table
    assert discord_out == expected_table


def test_escaped_url_in_link():
    """URL with escaped closing paren (Telegram escapes, Discord does not)."""
    markdown = "[link](http://example.com/a\\))b)"
    telegram_out = render_markdown_to_mdv2(markdown)
    discord_out = render_markdown_to_discord(markdown)

    assert telegram_out == "[link](http://example.com/a\\))b\\)"
    assert discord_out == "[link](http://example.com/a))b)"
