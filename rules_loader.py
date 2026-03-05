"""Load game rules from a dedicated markdown file."""

from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent / "rules.md"


def get_rules_markdown() -> str:
    """Return the full rules text (Brazilian Portuguese)."""
    return _RULES_PATH.read_text(encoding="utf-8")


# Single load at import for use as RulesMarkdown.BODY replacement
RULES_BODY = get_rules_markdown()
