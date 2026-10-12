"""Authorization layer for CineBot.

Two roles:
- admin: the single TELEGRAM_ADMIN_ID. Full access, including destructive
  actions and user management.
- user:  IDs from TELEGRAM_EXTRA_USERS (static, env) or added at runtime via
  /adduser (dynamic, persisted to a JSON file). Read + add content.

Everyone else is silently dropped by `gate`, which runs before every handler.
"""
import json
import logging
import os
import time
from functools import wraps

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from . import config

log = logging.getLogger(__name__)

# Callback data prefixes that trigger destructive actions (admin only).
ADMIN_CALLBACK_PREFIXES = ("qbt_", "del_")

_MAX_NOTIFIED = 500


class UserStore:
    def __init__(self, path: str, admin_id: int, static_ids: set[int]):
        self._path = path
        self.admin_id = admin_id
        self._static = set(static_ids) - {admin_id}
        self._dynamic: dict[int, dict] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.get("users", []):
                uid = int(entry["id"])
                self._dynamic[uid] = {
                    "id": uid,
                    "name": str(entry.get("name", "")),
                    "added_at": str(entry.get("added_at", "")),
                }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # Fail closed: keep only admin + static users, preserve the broken file.
            backup = f"{self._path}.corrupt-{int(time.time())}"
            log.exception("Users file %s is unreadable; moved to %s", self._path, backup)
            self._dynamic = {}
            try:
                os.replace(self._path, backup)
            except OSError:
                log.exception("Could not move corrupt users file")

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        tmp = f"{self._path}.tmp"
        payload = {"users": sorted(self._dynamic.values(), key=lambda u: u["id"])}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)

    def is_admin(self, uid: int) -> bool:
        return uid == self.admin_id

    def is_allowed(self, uid: int) -> bool:
        return uid == self.admin_id or uid in self._static or uid in self._dynamic

    def is_static(self, uid: int) -> bool:
        return uid in self._static

    def is_dynamic(self, uid: int) -> bool:
        return uid in self._dynamic

    def add(self, uid: int, name: str = "") -> bool:
        """Persists a user. Returns False if already admin or already persisted.

        Static (.env) users can be added too, so they can be migrated out of .env.
        """
        if uid == self.admin_id or uid in self._dynamic:
            return False
        self._dynamic[uid] = {
            "id": uid,
            "name": name,
            "added_at": time.strftime("%Y-%m-%d %H:%M"),
        }
        self._save()
        return True

    def remove(self, uid: int) -> bool:
        """Returns False if the user is not a dynamic user."""
        if uid not in self._dynamic:
            return False
        del self._dynamic[uid]
        self._save()
        return True

    def list_users(self) -> list[dict]:
        static = [
            {"id": uid, "name": "", "added_at": "", "static": True, "also_env": False}
            for uid in sorted(self._static - self._dynamic.keys())
        ]
        dynamic = [
            {**u, "static": False, "also_env": u["id"] in self._static}
            for u in sorted(self._dynamic.values(), key=lambda u: u["id"])
        ]
        return static + dynamic


store = UserStore(config.TELEGRAM_USERS_FILE, config.TELEGRAM_ADMIN_ID, config.TELEGRAM_EXTRA_USER_IDS)

_notified: set[int] = set()


def _uid(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def is_admin(update: Update) -> bool:
    uid = _uid(update)
    return uid is not None and store.is_admin(uid)


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs first (group -1). Drops every update from a non-authorized user."""
    uid = _uid(update)
    if uid is not None and store.is_allowed(uid):
        return

    user = update.effective_user
    username = f"@{user.username}" if user and user.username else "-"
    full_name = user.full_name if user else "-"
    log.warning("Unauthorized update dropped: id=%s username=%s name=%r", uid, username, full_name)

    # Tell the admin once per user per process, so they can grant access.
    if uid is not None and uid not in _notified:
        if len(_notified) >= _MAX_NOTIFIED:
            _notified.clear()
        _notified.add(uid)
        try:
            await context.bot.send_message(
                chat_id=store.admin_id,
                text=(
                    "Intento de acceso no autorizado\n"
                    f"Nombre: {full_name}\n"
                    f"Usuario: {username}\n"
                    f"ID: {uid}\n\n"
                    f"Para autorizarlo: /adduser {uid}"
                ),
            )
        except Exception:
            log.exception("Could not notify admin about unauthorized access")

    raise ApplicationHandlerStop


def admin_required(func):
    """Restricts a command handler to the admin."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not is_admin(update):
            log.warning("Non-admin %s tried admin command %s", _uid(update), func.__name__)
            if update.effective_message:
                await update.effective_message.reply_text("Solo el admin puede usar este comando.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
