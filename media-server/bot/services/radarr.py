import httpx

from ..config import RADARR_URL, RADARR_API_KEY


def _get(path: str, **params) -> dict:
    params["apiKey"] = RADARR_API_KEY
    r = httpx.get(f"{RADARR_URL}/api/v3{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(
        f"{RADARR_URL}/api/v3{path}",
        params={"apiKey": RADARR_API_KEY},
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
