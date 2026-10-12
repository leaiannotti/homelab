import httpx

from ..config import SONARR_URL, SONARR_API_KEY

# API key goes in a header, never in the URL (URLs end up in error messages/logs).
_HEADERS = {"X-Api-Key": SONARR_API_KEY}


def _get(path: str, **params) -> dict:
    r = httpx.get(f"{SONARR_URL}/api/v3{path}", params=params, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = httpx.post(
        f"{SONARR_URL}/api/v3{path}",
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
        headers=_HEADERS,
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


def series_exists(tvdb_id: int) -> bool:
    series = _get("/series")
    return any(s.get("tvdbId") == tvdb_id for s in series)


def get_history(page_size: int = 5) -> list[dict]:
    data = _get("/history", pageSize=page_size, sortKey="date", sortDirection="descending")
    return data.get("records", [])


def get_queue() -> list[dict]:
    data = _get("/queue", includeUnknownSeriesItems="true")
    return data.get("records", [])


def get_library_stats() -> dict:
    """Return total series, episode counts, and disk usage."""
    series_list = _get("/series")
    total = len(series_list)
    monitored = sum(1 for s in series_list if s.get("monitored"))
    total_eps = sum(s.get("statistics", {}).get("totalEpisodeCount", 0) for s in series_list)
    have_eps = sum(s.get("statistics", {}).get("episodeFileCount", 0) for s in series_list)
    size_bytes = sum(s.get("statistics", {}).get("sizeOnDisk", 0) for s in series_list)
    return {
        "total": total,
        "monitored": monitored,
        "total_eps": total_eps,
        "have_eps": have_eps,
        "size_bytes": size_bytes,
    }


def get_recent_series(limit: int = 5) -> list[dict]:
    """Return the most recently added series."""
    series_list = _get("/series")
    with_date = [s for s in series_list if s.get("added")]
    with_date.sort(key=lambda s: s["added"], reverse=True)
    return [
        {
            "title": s.get("title", "?"),
            "year": s.get("year", ""),
            "added": s["added"],
            "season_count": s.get("statistics", {}).get("seasonCount", 0),
        }
        for s in with_date[:limit]
    ]


def get_upcoming_episodes(days: int = 7) -> list[dict]:
    """Return upcoming episodes airing within the next N days."""
    from datetime import date, timedelta

    today = date.today()
    end = today + timedelta(days=days)
    data = _get(
        "/calendar",
        start=today.isoformat(),
        end=end.isoformat(),
        unmonitored="false",
    )
    episodes = []
    for ep in data:
        air_raw = ep.get("airDate") or ep.get("airDateUtc", "")
        try:
            air = date.fromisoformat(air_raw[:10])
        except ValueError:
            continue
        series = ep.get("series", {})
        episodes.append({
            "series": series.get("title", ep.get("seriesTitle", "?")),
            "season": ep.get("seasonNumber", 0),
            "episode": ep.get("episodeNumber", 0),
            "title": ep.get("title", ""),
            "air_date": air.isoformat(),
        })
    episodes.sort(key=lambda x: x["air_date"])
    return episodes[:10]


def delete_series(sonarr_id: int, delete_files: bool = True) -> None:
    r = httpx.delete(
        f"{SONARR_URL}/api/v3/series/{sonarr_id}",
        headers=_HEADERS, params={"deleteFiles": str(delete_files).lower()},
        timeout=15,
    )
    r.raise_for_status()


def get_series_list() -> list[dict]:
    """Return all series with id, title, year, tvdbId."""
    series_list = _get("/series")
    return [
        {
            "id": s["id"],
            "title": s.get("title", "?"),
            "year": s.get("year", ""),
            "tvdb_id": s.get("tvdbId"),
            "monitored": s.get("monitored", False),
            "season_count": s.get("statistics", {}).get("seasonCount", 0),
        }
        for s in series_list
    ]
