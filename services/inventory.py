"""Inventory service for NyaBot.

Supports the two inventory shapes present in the legacy bot:
- counted collections: {"item": count}
- owned-item lists: ["item1", "item2"]
"""
import threading

_db = None
_db_lock = threading.RLock()
_mark_dirty = lambda: None

def configure(*, db, db_lock=None, mark_dirty=None):
    global _db, _db_lock, _mark_dirty
    _db = db
    _db_lock = db_lock or threading.RLock()
    _mark_dirty = mark_dirty or (lambda: None)

def add_item(inventory, item_name, amount=1):
    amount = int(amount)
    if amount < 0:
        raise ValueError("amount must be >= 0")
    if isinstance(inventory, dict):
        inventory[item_name] = int(inventory.get(item_name, 0) or 0) + amount
        return inventory[item_name]
    if isinstance(inventory, list):
        for _ in range(amount):
            inventory.append(item_name)
        return inventory.count(item_name)
    raise TypeError("inventory must be a dict or list")

def remove_item(inventory, item_name, amount=1):
    amount = int(amount)
    if amount <= 0:
        return False
    if isinstance(inventory, dict):
        current = int(inventory.get(item_name, 0) or 0)
        if current < amount:
            return False
        remaining = current - amount
        if remaining:
            inventory[item_name] = remaining
        else:
            inventory.pop(item_name, None)
        return True
    if isinstance(inventory, list):
        if inventory.count(item_name) < amount:
            return False
        for _ in range(amount):
            inventory.remove(item_name)
        return True
    raise TypeError("inventory must be a dict or list")

def has_item(inventory, item_name, amount=1):
    amount = int(amount)
    if isinstance(inventory, dict):
        return int(inventory.get(item_name, 0) or 0) >= amount
    if isinstance(inventory, list):
        return inventory.count(item_name) >= amount
    return False

def add_to_user_inventory(econ, item_name, amount=1):
    with _db_lock:
        inventory = econ.setdefault("inventory", [])
        value = add_item(inventory, item_name, amount)
        _mark_dirty()
        return value

def remove_from_user_inventory(econ, item_name, amount=1):
    with _db_lock:
        inventory = econ.setdefault("inventory", [])
        if not remove_item(inventory, item_name, amount):
            return False
        _mark_dirty()
        return True

def user_has_item(econ, item_name, amount=1):
    return has_item(econ.setdefault("inventory", []), item_name, amount)

def add_counted_item(collection, item_name, amount=1):
    """Used for fish/hunt/backpack-style counted collections."""
    with _db_lock:
        value = add_item(collection, item_name, amount)
        _mark_dirty()
        return value

def add_list_entitlement(econ, field, item_id):
    with _db_lock:
        items = econ.setdefault(field, [])
        if item_id not in items:
            items.append(item_id)
            _mark_dirty()
            return True
        return False

def remove_list_entitlement(econ, field, item_id):
    with _db_lock:
        items = econ.setdefault(field, [])
        if item_id not in items:
            return False
        items.remove(item_id)
        _mark_dirty()
        return True

__all__ = [
    "configure", "add_item", "remove_item", "has_item",
    "add_to_user_inventory", "remove_from_user_inventory", "user_has_item",
    "add_counted_item", "add_list_entitlement", "remove_list_entitlement",
]
