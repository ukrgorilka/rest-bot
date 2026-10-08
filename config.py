"""NyaBot configuration.

All environment-backed settings are kept here so the bot launcher and
application modules use one configuration source during the migration.
"""

import os
from datetime import timedelta, timezone


def normalize_tg_id(value):
    """Normalize Telegram chat/channel IDs to int."""
    if not value:
        return 0
    raw = str(value).strip()
    try:
        number = int(raw)
        # Convert old-style negative IDs to Telegram's -100... format.
        if number < 0 and not str(number).startswith("-100") and len(str(abs(number))) >= 9:
            return int(f"-100{abs(number)}")
        return number
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

BOT_VERSION = "0.3"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

_CONFIG_PROBLEMS = []

def _env_int(name, default, *, minimum=None):
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        _CONFIG_PROBLEMS.append(f"{name} must be an integer; using safe default {default}")
        value = int(default)
    if minimum is not None and value < minimum:
        _CONFIG_PROBLEMS.append(f"{name} must be >= {minimum}; using safe default {default}")
        value = int(default)
    return value


def _env_float(name, default, *, minimum=None):
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _CONFIG_PROBLEMS.append(f"{name} must be a number; using safe default {default}")
        value = float(default)
    if minimum is not None and value < minimum:
        _CONFIG_PROBLEMS.append(f"{name} must be >= {minimum}; using safe default {default}")
        value = float(default)
    return value


ADMIN_ID = _env_int("ADMIN_ID", 6081930693, minimum=1)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "ukrgorilka").strip().lstrip("@")

# ---------------------------------------------------------------------------
# Database / persistence
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATA_FILE = os.environ.get("DATA_FILE", "rests_data.json").strip() or "rests_data.json"
# Neon is the live source of truth in production. JSON bootstrap is opt-in only.
ALLOW_JSON_BOOTSTRAP = os.environ.get("ALLOW_JSON_BOOTSTRAP", "").strip().lower() in {"1", "true", "yes", "on"}

# Optional Telegram JSON backup channel.
DB_CHANNEL_ID = normalize_tg_id(os.environ.get("DB_CHANNEL_ID", "0"))

# ---------------------------------------------------------------------------
# Telegram chats / logging
# ---------------------------------------------------------------------------

LOG_CHANNEL_ID = normalize_tg_id(
    os.environ.get("LOG_CHANNEL_ID", "-1004369517562")
)

VD_CHAT_ID = normalize_tg_id(
    os.environ.get("VD_CHAT_ID", "-1003703264754")
)

MEDIA_TG_CHAT_ID = normalize_tg_id(
    os.environ.get("MEDIA_TG_CHAT_ID", "-1004311479842")
)

# ---------------------------------------------------------------------------
# Mini App
# ---------------------------------------------------------------------------

PORT = _env_int("PORT", 8080, minimum=1)

MINIAPP_URL = (
    os.environ.get("MINIAPP_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or ""
).strip().rstrip("/")

MINIAPP_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "miniapp",
)

MINIAPP_GAME_TTL = 2 * 60 * 60
MINIAPP_DAILY_REWARD_CAP = 5000

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

MSK_TZ = timezone(timedelta(hours=3))


def now_msk():
    """Return current time in UTC+3."""
    from datetime import datetime
    return datetime.now(MSK_TZ)


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

AUTOSAVE_INTERVAL = _env_float("AUTOSAVE_INTERVAL", 5.0, minimum=0.1)
AUTOSAVE_DEBOUNCE = _env_float("AUTOSAVE_DEBOUNCE", 25.0, minimum=0.0)
BACKUP_INTERVAL = _env_float("BACKUP_INTERVAL", 7200.0, minimum=0.0)

# Telegram handler/polling resilience. The bot has synchronous handlers that
# may perform DB/Telegram I/O. Keep enough workers so slow handlers cannot
# consume the whole pool, and restart the process on a sustained backlog.
BOT_HANDLER_THREADS = _env_int("BOT_HANDLER_THREADS", 8, minimum=2)
BOT_HANDLER_BACKLOG_LIMIT = _env_int("BOT_HANDLER_BACKLOG_LIMIT", 200, minimum=10)
BOT_HANDLER_BACKLOG_GRACE = _env_float("BOT_HANDLER_BACKLOG_GRACE", 120.0, minimum=30.0)
POLLING_TIMEOUT = _env_int("POLLING_TIMEOUT", 20, minimum=5)

BUSINESS_TAX_RATE = min(0.75, max(0.0, _env_float("BUSINESS_TAX_RATE", 0.20, minimum=0.0)))
BUSINESS_SELL_RATE = min(1.0, max(0.0, _env_float("BUSINESS_SELL_RATE", 0.80, minimum=0.0)))


def validate():
    """Return all configuration problems without crashing during import."""
    problems = list(_CONFIG_PROBLEMS)

    if not BOT_TOKEN:
        problems.append("BOT_TOKEN is not set")

    if not DATABASE_URL:
        problems.append(
            "DATABASE_URL is not set; Neon is unavailable. Local JSON fallback "
            "is disabled by default and must be explicitly enabled for local testing."
        )

    return problems
