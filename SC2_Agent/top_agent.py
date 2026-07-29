"""Summary-only strategy file parsing."""

from __future__ import annotations

import re
from typing import Optional


_SUMMARY_HEADER_RE = re.compile(
    r"^\s*#\s*(?:\u6458\u8981|Summary|Abstract)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_ANY_HEADER_RE = re.compile(
    r"^\s*#\s+.+$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_strategy_summary(text: str) -> str:
    """Return the content under ``# Summary``.

    Summary-only files are the canonical format. A heading-less file is
    accepted as a migration fallback; any second heading terminates the
    summary so content outside it never enters a decision prompt.
    """
    if not text:
        return ""
    raw = text.strip()
    summary_match = _SUMMARY_HEADER_RE.search(raw)
    if summary_match is None:
        return raw
    start = summary_match.end()
    next_header: Optional[re.Match[str]] = _ANY_HEADER_RE.search(raw, start)
    end = next_header.start() if next_header else len(raw)
    return raw[start:end].strip()


__all__ = ["parse_strategy_summary"]
