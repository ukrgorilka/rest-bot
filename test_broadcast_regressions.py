"""Isolated regression tests for broadcast delivery failures and production web serving."""
from __future__ import annotations

import ast
import threading
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent
source = (ROOT / "newfile.py").read_text(encoding="utf-8")
tree = ast.parse(source)
names = {"_broadcast_chat_is_active", "_known_broadcast_chat_ids", "_broadcast_error_means_inactive", "_mark_broadcast_inactive", "broadcast_system_message"}
selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
ns = {"db_lock": threading.RLock(), "db": {}, "time": time, "mark_dirty": lambda: None, "bot": None}
exec(compile(ast.Module(body=selected, type_ignores=[]), "broadcast_regression.py", "exec"), ns)

class ForbiddenBlocked(Exception):
    error_code = 403
    description = "Forbidden: bot was blocked by the user"

class FakeBot:
    def __init__(self):
        self.calls = []
    def send_message(self, chat_id, *args, **kwargs):
        self.calls.append(chat_id)
        if chat_id == 123:
            raise ForbiddenBlocked("blocked")
        return True

ns["db"].update({
    "economy": {
        "123": {"chat_ids": [123], "balance": 999},
        "456": {"chat_ids": [456], "balance": 888},
    },
    "bot_chats": {
        "-1001": {"chat_id": -1001, "status": "active"},
    },
})
ns["bot"] = FakeBot()

sent, failed = ns["broadcast_system_message"]("test")
assert failed == 1, (sent, failed)
assert ns["db"]["economy"]["123"]["broadcast_status"] == "inactive"
assert ns["db"]["economy"]["123"]["balance"] == 999
assert 123 not in ns["_known_broadcast_chat_ids"]()
assert 456 in ns["_known_broadcast_chat_ids"]()
assert -1001 in ns["_known_broadcast_chat_ids"]()

# A second broadcast must not call Telegram for the blocked user again.
ns["bot"].calls.clear()
ns["broadcast_system_message"]("test2")
assert 123 not in ns["bot"].calls, ns["bot"].calls

print("broadcast 403 regression: PASS")
