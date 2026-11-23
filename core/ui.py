"""Shared Telegram HTML UI formatting helpers for NyaBot v1.0+.

Provides clean blockquote cards, expandable lists, visual progress bars,
sparkline trend graphs, and human-readable duration formatting.
"""

from __future__ import annotations

import html
import math


_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def progress_bar(current, total, width=10, filled="▰", empty="▱", show_percent=True):
    """Render a compact Unicode progress bar with optional percentage."""
    try:
        cur = float(current)
        tot = float(total)
    except (TypeError, ValueError):
        cur, tot = 0.0, 1.0
    if not math.isfinite(cur):
        cur = 0.0
    if not math.isfinite(tot) or tot <= 0:
        tot = 1.0
    ratio = max(0.0, min(1.0, cur / tot))
    width = max(4, min(20, int(width)))
    fill_count = int(round(ratio * width))
    bar = (filled * fill_count) + (empty * (width - fill_count))
    if show_percent:
        return f"{bar} {int(round(ratio * 100))}%"
    return bar


def sparkline(values):
    """Render a compact Unicode sparkline from a sequence of numbers."""
    clean = []
    for val in values or ():
        try:
            num = float(val)
            if math.isfinite(num):
                clean.append(num)
        except (TypeError, ValueError):
            continue
    if not clean:
        return "▁▁▁▁▁"
    lo = min(clean)
    hi = max(clean)
    if hi - lo <= 1e-9:
        return _SPARK_BLOCKS[3] * len(clean)
    chars = []
    span = hi - lo
    max_idx = len(_SPARK_BLOCKS) - 1
    for num in clean:
        idx = int(round(((num - lo) / span) * max_idx))
        chars.append(_SPARK_BLOCKS[max(0, min(max_idx, idx))])
    return "".join(chars)


def format_duration(seconds):
    """Format a positive duration in seconds into compact Russian text."""
    remaining = max(1, int(math.ceil(float(seconds))))
    days, rem = divmod(remaining, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days} дн. {hours} ч." if hours else f"{days} дн."
    if hours:
        return f"{hours} ч. {minutes} мин." if minutes else f"{hours} ч."
    if minutes:
        return f"{minutes} мин. {secs} сек." if secs else f"{minutes} мин."
    return f"{secs} сек."


def quote(content, expandable=False):
    """Wrap pre-formatted HTML text in a Telegram blockquote."""
    text = str(content or "").strip()
    if not text:
        return ""
    tag = "<blockquote expandable>" if expandable else "<blockquote>"
    return f"{tag}{text}</blockquote>"


def card(title, body=None, expandable=None, footer=None):
    """Assemble a clean modern Telegram HTML card without heavy ASCII lines."""
    parts = [str(title).strip()]
    if body:
        if isinstance(body, (list, tuple)):
            body_text = "\n".join(str(line) for line in body if line is not None and str(line) != "")
        else:
            body_text = str(body)
        if body_text.strip():
            parts.append(quote(body_text, expandable=False))
    if expandable:
        if isinstance(expandable, (list, tuple)):
            exp_text = "\n".join(str(line) for line in expandable if line is not None and str(line) != "")
        else:
            exp_text = str(expandable)
        if exp_text.strip():
            parts.append(quote(exp_text, expandable=True))
    if footer:
        parts.append(str(footer).strip())
    return "\n\n".join(p for p in parts if p)


def safe_name(value, fallback="Пользователь", max_len=64):
    """Escape a display name safely for Telegram HTML."""
    raw = str(value or "").strip() or fallback
    return html.escape(raw[:max_len])


def badge_prefix(econ, achievements_catalog=None):
    """Return the user's selected achievement badge prefix, if unlocked."""
    if not isinstance(econ, dict):
        return ""
    badge_id = econ.get("active_badge")
    if not badge_id or not isinstance(badge_id, str):
        return ""
    unlocked = econ.get("achievements", [])
    if not isinstance(unlocked, (list, tuple, set)):
        return ""
    if badge_id not in unlocked:
        return ""
    if isinstance(achievements_catalog, dict) and badge_id in achievements_catalog:
        title = str(achievements_catalog[badge_id].get("title", "")).strip()
        if title:
            icon = title.split()[0]
            return f"{icon} "
    return "🏅 "
