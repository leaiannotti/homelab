import httpx

from ..config import RADARR_URL, RADARR_API_KEY

# API key goes in a header, never in the URL (URLs end up in error messages/logs).
_HEADERS = {"X-Api-Key": RADARR_API_KEY}


def _get(path: str, **params) -> dict:
    r = httpx.get(f"{RADARR_URL}/api/v3{path}", params=params, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(
        f"{RADARR_URL}/api/v3{path}",
        headers=_HEADERS,
        json=body,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_root_folder() -> dict:
    folders = _get("/rootfolder")
    return folders[0]


def get_quality_profile() -> dict:
    profiles = _get("/qualityprofile")
    return profiles[0]


def add_movie(tmdb_id: int) -> str:
    root = get_root_folder()
    profile = get_quality_profile()

    body = {
        "tmdbId": tmdb_id,
        "title": "",
        "qualityProfileId": profile["id"],
        "rootFolderPath": root["path"],
        "monitored": True,
        "addOptions": {"searchForMovie": True},
    }

    movie = _post("/movie", body)
    return movie.get("title", "Unknown")


def lookup_movie(term: str) -> list[dict]:
    data = _get("/movie/lookup", term=term)
    return data[:5]


def get_queue() -> list[dict]:
    data = _get("/queue", includeUnknownMovieItems="true")
    return data.get("records", [])


def get_calendar() -> list[dict]:
    from datetime import date, timedelta

    today = date.today()
    end = today + timedelta(days=30)
    data = _get(
        "/calendar",
        start=today.isoformat(),
        end=end.isoformat(),
        unmonitored="false",
    )
    return data[:5]


def movie_exists(tmdb_id: int) -> bool:
    movies = _get("/movie")
    return any(m.get("tmdbId") == tmdb_id for m in movies)


def get_all_movies() -> dict[int, str]:
    movies = _get("/movie")
    return {m["id"]: m.get("title", "?") for m in movies}


def get_history(page_size: int = 5) -> list[dict]:
    data = _get("/history", pageSize=page_size, sortKey="date", sortDirection="descending")
    return data.get("records", [])


def get_library_stats() -> dict:
    """Return total movies, monitored count, and disk usage."""
    movies = _get("/movie")
    total = len(movies)
    monitored = sum(1 for m in movies if m.get("monitored"))
    size_bytes = sum(
        m.get("movieFile", {}).get("size", 0) or 0
        for m in movies
        if m.get("hasFile")
    )
    has_file = sum(1 for m in movies if m.get("hasFile"))
    return {
        "total": total,
        "monitored": monitored,
        "has_file": has_file,
        "size_bytes": size_bytes,
    }


def get_recent_movies(limit: int = 5) -> list[dict]:
    """Return the most recently added movies."""
    movies = _get("/movie")
    with_date = [m for m in movies if m.get("added") and m.get("hasFile")]
    with_date.sort(key=lambda m: m["added"], reverse=True)
    return [
        {"title": m.get("title", "?"), "year": m.get("year", ""), "added": m["added"]}
        for m in with_date[:limit]
    ]


def get_upcoming_movies(days: int = 60) -> list[dict]:
    """Return monitored movies with an upcoming digital/cinema release."""
    from datetime import date, timedelta, timezone
    import re

    today = date.today()
    cutoff = today + timedelta(days=days)
    movies = _get("/movie")
    upcoming = []
    for m in movies:
        if not m.get("monitored") or m.get("hasFile"):
            continue
        # Check digitalRelease or inCinemas
        for field in ("digitalRelease", "physicalRelease", "inCinemas"):
            raw = m.get(field)
            if not raw:
                continue
            try:
                d = date.fromisoformat(raw[:10])
            except ValueError:
                continue
            if today <= d <= cutoff:
                upcoming.append({
                    "title": m.get("title", "?"),
                    "year": m.get("year", ""),
                    "release_date": d.isoformat(),
                    "release_type": field,
                })
                break
    upcoming.sort(key=lambda x: x["release_date"])
    return upcoming[:10]


def delete_movie(radarr_id: int, delete_files: bool = True) -> None:
    r = httpx.delete(
        f"{RADARR_URL}/api/v3/movie/{radarr_id}",
        headers=_HEADERS, params={"deleteFiles": str(delete_files).lower()},
        timeout=15,
    )
    r.raise_for_status()


def get_movies_list() -> list[dict]:
    """Return all movies with id, title, year, tmdbId, hasFile."""
    movies = _get("/movie")
    return [
        {
            "id": m["id"],
            "title": m.get("title", "?"),
            "year": m.get("year", ""),
            "tmdb_id": m.get("tmdbId"),
            "has_file": m.get("hasFile", False),
            "monitored": m.get("monitored", False),
        }
        for m in movies
    ]
