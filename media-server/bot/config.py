import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


TELEGRAM_BOT_TOKEN = require("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = int(require("TELEGRAM_ADMIN_ID"))
TELEGRAM_EXTRA_USERS = os.getenv("TELEGRAM_EXTRA_USERS", "")
TELEGRAM_ALLOWED_IDS = {TELEGRAM_ADMIN_ID}
if TELEGRAM_EXTRA_USERS:
    for uid in TELEGRAM_EXTRA_USERS.split(","):
        try:
            TELEGRAM_ALLOWED_IDS.add(int(uid.strip()))
        except ValueError:
            pass

TMDB_API_KEY = require("TMDB_API_KEY")

RADARR_URL = require("RADARR_URL").rstrip("/")
RADARR_API_KEY = require("RADARR_API_KEY")

SONARR_URL = require("SONARR_URL").rstrip("/")
SONARR_API_KEY = require("SONARR_API_KEY")
