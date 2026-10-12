import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))


def require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


TELEGRAM_BOT_TOKEN = require("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = int(require("TELEGRAM_ADMIN_ID"))


def _parse_ids(raw: str, key: str) -> set[int]:
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise ValueError(f"Invalid Telegram user ID in {key}: {part!r}")
    return ids


# Static users (role "user"), always allowed, not removable from chat.
TELEGRAM_EXTRA_USER_IDS = _parse_ids(os.getenv("TELEGRAM_EXTRA_USERS", ""), "TELEGRAM_EXTRA_USERS")
# Users added from chat via /adduser are persisted here (outside bot/ so deploys don't overwrite it).
TELEGRAM_USERS_FILE = os.getenv(
    "TELEGRAM_USERS_FILE",
    os.path.join(BASE_DIR, "config", "cinebot", "users.json"),
)

TMDB_API_KEY = require("TMDB_API_KEY")

RADARR_URL = require("RADARR_URL").rstrip("/")
RADARR_API_KEY = require("RADARR_API_KEY")

SONARR_URL = require("SONARR_URL").rstrip("/")
SONARR_API_KEY = require("SONARR_API_KEY")

QBITTORRENT_URL = os.getenv("QBITTORRENT_URL", "http://localhost:8080").rstrip("/")
QBITTORRENT_USER = require("QBITTORRENT_USER")
QBITTORRENT_PASS = require("QBITTORRENT_PASS")
