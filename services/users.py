"""Compatibility boundary for NyaBot user records.

The existing get_user_econ() in newfile.py remains canonical while the
refactor is staged, because it contains migrations/defaulting that must not be
duplicated.
"""
from __future__ import annotations

_get_user_econ_impl = None
_get_global_user_key_impl = None
_merge_user_econ_data_impl = None
_clean_tag = lambda value: str(value or "").strip().lstrip("@")

def configure(*, get_user_econ=None, get_global_user_key=None, merge_user_econ_data=None, clean_tag=None):
    global _get_user_econ_impl, _get_global_user_key_impl, _merge_user_econ_data_impl, _clean_tag
    _get_user_econ_impl = get_user_econ
    _get_global_user_key_impl = get_global_user_key
    _merge_user_econ_data_impl = merge_user_econ_data
    if clean_tag is not None:
        _clean_tag = clean_tag

def get_global_user_key(user_id=None, user_tag=None):
    if _get_global_user_key_impl is not None:
        return _get_global_user_key_impl(user_id, user_tag)
    if user_id:
        return f"id_{user_id}"
    if user_tag:
        return f"tag_{_clean_tag(user_tag).lower()}"
    return "unknown_user"

def get_user_econ(user_id=None, user_tag=None, username=None):
    if _get_user_econ_impl is None:
        raise RuntimeError("services.users.configure() requires get_user_econ")
    return _get_user_econ_impl(user_id, user_tag, username)

def get_balance(econ):
    return int(econ.get("balance", 0) or 0)

def set_balance(econ, amount, *, mark_dirty=None):
    econ["balance"] = max(0, int(amount or 0))
    if mark_dirty:
        mark_dirty()
    return econ["balance"]

def add_balance(econ, amount, *, mark_dirty=None):
    econ["balance"] = max(0, get_balance(econ) + int(amount or 0))
    if mark_dirty:
        mark_dirty()
    return econ["balance"]

def update_fields(econ, *, mark_dirty=None, **fields):
    econ.update(fields)
    if mark_dirty:
        mark_dirty()
    return econ

def merge_user_econ_data(dest, src):
    if _merge_user_econ_data_impl is None:
        raise RuntimeError("services.users.configure() requires merge_user_econ_data")
    return _merge_user_econ_data_impl(dest, src)

__all__ = [
    "configure", "get_global_user_key", "get_user_econ", "get_balance",
    "set_balance", "add_balance", "update_fields", "merge_user_econ_data",
]
