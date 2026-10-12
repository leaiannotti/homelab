import httpx

from ..config import QBITTORRENT_URL, QBITTORRENT_USER, QBITTORRENT_PASS

_SESSION_COOKIE: str | None = None
_SESSION_COOKIE_NAME: str = "SID"


def _login() -> str:
    global _SESSION_COOKIE, _SESSION_COOKIE_NAME
    r = httpx.post(
        f"{QBITTORRENT_URL}/api/v2/auth/login",
        data={"username": QBITTORRENT_USER, "password": QBITTORRENT_PASS},
        timeout=10,
    )
    r.raise_for_status()
    # Older versions return "Ok.", newer return 204 with empty body — both are valid
    if r.status_code not in (200, 204) or r.text.strip() == "Fails.":
        raise RuntimeError("qBittorrent login failed")
    # Cookie name changed in newer versions: QBT_SID_<port> instead of SID
    cookie = None
    for name, value in r.cookies.items():
        if "SID" in name:
            cookie = value
            _SESSION_COOKIE_NAME = name
            break
    if not cookie:
        raise RuntimeError("No SID cookie in qBittorrent response")
    _SESSION_COOKIE = cookie
    return cookie


def _get_cookie() -> str:
    global _SESSION_COOKIE
    if _SESSION_COOKIE:
        return _SESSION_COOKIE
    return _login()


def _get(path: str, **params) -> httpx.Response:
    cookie = _get_cookie()
    r = httpx.get(
        f"{QBITTORRENT_URL}/api/v2{path}",
        params=params or None,
        cookies={_SESSION_COOKIE_NAME: cookie},
        timeout=15,
    )
    if r.status_code == 403:
        # Session expired — re-login once
        cookie = _login()
        r = httpx.get(
            f"{QBITTORRENT_URL}/api/v2{path}",
            params=params or None,
            cookies={_SESSION_COOKIE_NAME: cookie},
            timeout=15,
        )
    r.raise_for_status()
    return r


def _post(path: str, data: dict | None = None) -> httpx.Response:
    cookie = _get_cookie()
    r = httpx.post(
        f"{QBITTORRENT_URL}/api/v2{path}",
        data=data,
        cookies={_SESSION_COOKIE_NAME: cookie},
        timeout=15,
    )
    if r.status_code == 403:
        cookie = _login()
        r = httpx.post(
            f"{QBITTORRENT_URL}/api/v2{path}",
            data=data,
            cookies={_SESSION_COOKIE_NAME: cookie},
            timeout=15,
        )
    r.raise_for_status()
    return r


def get_torrents() -> list[dict]:
    """Return all torrents with state, progress, speed, size."""
    r = _get("/torrents/info")
    return r.json()


def get_main_data() -> dict:
    """Return global transfer info (speeds, free space, etc.)."""
    r = _get("/transfer/info")
    return r.json()


def pause_torrent(torrent_hash: str) -> None:
    _post("/torrents/pause", {"hashes": torrent_hash})


def resume_torrent(torrent_hash: str) -> None:
    _post("/torrents/resume", {"hashes": torrent_hash})


def delete_torrent(torrent_hash: str, delete_files: bool = False) -> None:
    _post("/torrents/delete", {
        "hashes": torrent_hash,
        "deleteFiles": "true" if delete_files else "false",
    })


def delete_torrents(hashes: set[str], delete_files: bool = True) -> tuple[int, int]:
    """Delete the given torrents (ignores hashes qBittorrent doesn't have).

    Returns (deleted_count, freed_bytes).
    """
    wanted = {h.lower() for h in hashes}
    present = [t for t in get_torrents() if t.get("hash", "").lower() in wanted]
    if not present:
        return 0, 0
    _post("/torrents/delete", {
        "hashes": "|".join(t["hash"] for t in present),
        "deleteFiles": "true" if delete_files else "false",
    })
    return len(present), sum(t.get("size", 0) for t in present)


def format_speed(bps: int) -> str:
    if bps >= 1_048_576:
        return f"{bps / 1_048_576:.1f} MB/s"
    if bps >= 1024:
        return f"{bps / 1024:.0f} KB/s"
    return f"{bps} B/s"


def format_size(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f} MB"
    return f"{b / 1024:.0f} KB"


STATE_ICON = {
    "downloading": "⬇️",
    "stalledDL": "⏸",
    "uploading": "⬆️",
    "stalledUP": "⬆️",
    "pausedDL": "⏸",
    "pausedUP": "✅",
    "queuedDL": "🕐",
    "queuedUP": "🕐",
    "checkingDL": "🔍",
    "checkingUP": "🔍",
    "error": "❌",
    "missingFiles": "❌",
    "moving": "📦",
    "unknown": "❓",
}
