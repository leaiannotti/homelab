import httpx

from ..config import SONARR_URL, SONARR_API_KEY


def _get(path: str, **params) -> dict:
    params["apiKey"] = SONARR_API_KEY
    r = httpx.get(f"{SONARR_URL}/api/v3{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(
        f"{SONARR_URL}/api/v3{path}",
        params={"apiKey": SONARR_API_KEY},
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


def lookup_series(term: str) -> list[dict]:
    data = _get("/series/lookup", term=term)
    return data[:5]


def add_series(tvdb_id: int, title: str = "") -> str:
    result = add_series_full(tvdb_id, title)
    return result["title"]


def add_series_full(tvdb_id: int, title: str = "") -> dict:
    root = get_root_folder()
    profile = get_quality_profile()

    body = {
        "tvdbId": tvdb_id,
        "title": title,
        "qualityProfileId": profile["id"],
        "rootFolderPath": root["path"],
        "monitored": True,
        "addOptions": {
            "searchForMissingEpisodes": True,
            "searchForCutoffUnmetEpisodes": True,
        },
    }

    series = _post("/series", body)
    return series


def add_series_with_seasons(tvdb_id: int, season_numbers: list[int], title: str = "") -> str:
    existing = series_exists(tvdb_id)
    if existing:
        series = _get("/series")
        match = next((s for s in series if s.get("tvdbId") == tvdb_id), None)
        if match:
            for s in match.get("seasons", []):
                s["monitored"] = s.get("seasonNumber", 0) in season_numbers
            _put(f"/series/{match['id']}", match)
            return match.get("title", title)

    series = add_series_full(tvdb_id, title)
    series_id = series["id"]
    if "seasons" in series:
        for s in series["seasons"]:
            s["monitored"] = s.get("seasonNumber", 0) in season_numbers
    _put(f"/series/{series_id}", series)
    return series.get("title", title)


def _put(path: str, body: dict) -> dict:
    r = httpx.put(
        f"{SONARR_URL}/api/v3{path}",
        params={"apiKey": SONARR_API_KEY},
        json=body,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_series_season_status(tvdb_id: int) -> dict[str, list[dict]]:
    series_list = _get("/series")
    match = next((s for s in series_list if s.get("tvdbId") == tvdb_id), None)
    if not match:
        return {"found": False, "seasons": []}
    seasons = []
    for s in match.get("seasons", []):
        sn = s.get("seasonNumber", 0)
        if sn > 0:
            seasons.append({
                "season_number": sn,
                "monitored": s.get("monitored", False),
                "has_files": s.get("statistics", {}).get("episodeFileCount", 0) > 0,
                "total_episodes": s.get("statistics", {}).get("totalEpisodeCount", 0),
            })
    return {"found": True, "title": match.get("title", ""), "seasons": seasons}
    data = _get("/queue", includeUnknownSeriesItems="true")
    return data.get("records", [])


def series_exists(tvdb_id: int) -> bool:
    series = _get("/series")
    return any(s.get("tvdbId") == tvdb_id for s in series)


def get_history(page_size: int = 5) -> list[dict]:
    data = _get("/history", pageSize=page_size, sortKey="date", sortDirection="descending")
    return data.get("records", [])


def get_queue() -> list[dict]:
    data = _get("/queue", includeUnknownSeriesItems="true")
    return data.get("records", [])
