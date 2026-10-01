"""Minimal Telegram Bot API helpers for features not exposed by pyTelegramBotAPI yet.
All calls use the existing bot token; no extra third-party dependency is required.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request

_TOKEN = None
_BASE = "https://api.telegram.org/bot{}"

def configure(token: str) -> None:
    global _TOKEN
    _TOKEN = str(token or "").strip()

def _call(method: str, payload: dict) -> object:
    if not _TOKEN:
        raise RuntimeError("Telegram Bot token is not configured")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _BASE.format(_TOKEN) + "/" + method,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {raw[:500]}") from exc
    result = json.loads(raw)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {result.get('description', 'unknown error')}")
    return result.get("result")

def get_available_gifts():
    return _call("getAvailableGifts", {})

def send_gift(user_id: int, gift_id: str, text: str = ""):
    return _call("sendGift", {
        "user_id": int(user_id),
        "gift_id": str(gift_id),
        "text": str(text or "")[:128],
    })

def send_ephemeral_group_message(chat_id: int, receiver_user_id: int, callback_query_id: str, text: str):
    return _call("sendMessage", {
        "chat_id": int(chat_id),
        "text": str(text or "")[:4096],
        "parse_mode": "HTML",
        "ephemeral_message_parameters": {
            "receiver_user_id": int(receiver_user_id),
            "callback_query_id": str(callback_query_id),
            "replace_callback_query_message": True,
        },
    })

def refund_star_payment(user_id: int, telegram_payment_charge_id: str):
    return _call("refundStarPayment", {
        "user_id": int(user_id),
        "telegram_payment_charge_id": str(telegram_payment_charge_id),
    })
