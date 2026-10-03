"""Word-level diff rendering for the rewrite tab.

Kept free of Streamlit imports so it can be unit tested directly: importing
``app.py`` would execute the whole page script.
"""

import difflib
from html import escape

# Additions read green; removals read red and struck through.
ADDED_STYLE = "background:#d7f5d7;color:#1a5c1a;border-radius:3px;padding:1px 4px"
REMOVED_STYLE = (
    "background:#ffd7d7;color:#8b0000;text-decoration:line-through;"
    "border-radius:3px;padding:1px 4px"
)


def _span(text: str, style: str) -> str:
    """Wrap text in a styled span, escaped so model output cannot inject HTML."""
    return f'<span style="{style}">{escape(text)}</span>'


def render_word_diff(source: str, rewritten: str) -> str:
    """Return an escaped, word-level HTML diff between two texts."""
    source_words = source.split()
    rewritten_words = rewritten.split()
    matcher = difflib.SequenceMatcher(None, source_words, rewritten_words)

    parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(escape(" ".join(source_words[i1:i2])))
        elif tag == "replace":
            parts.append(_span(" ".join(source_words[i1:i2]), REMOVED_STYLE))
            parts.append(_span(" ".join(rewritten_words[j1:j2]), ADDED_STYLE))
        elif tag == "insert":
            parts.append(_span(" ".join(rewritten_words[j1:j2]), ADDED_STYLE))
        elif tag == "delete":
            parts.append(_span(" ".join(source_words[i1:i2]), REMOVED_STYLE))

    return " ".join(part for part in parts if part)
