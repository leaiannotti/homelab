from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import TMDB_API_KEY

BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


@dataclass
class Movie:
    tmdb_id: int
    title: str
    year: str
    overview: str
    rating: float
    poster_path: Optional[str]
    backdrop_path: Optional[str]

    @property
    def poster_url(self) -> Optional[str]:
        if self.poster_path:
            return f"{IMAGE_BASE}/w500{self.poster_path}"
        return None

    @property
    def backdrop_url(self) -> Optional[str]:
        if self.backdrop_path:
            return f"{IMAGE_BASE}/w1280{self.backdrop_path}"
        return None


@dataclass
class Person:
    tmdb_id: int
    name: str
    known_for: str
    profile_path: Optional[str]

    @property
    def profile_url(self) -> Optional[str]:
        if self.profile_path:
            return f"{IMAGE_BASE}/w200{self.profile_path}"
        return None


@dataclass
class TVShow:
    tmdb_id: int
    name: str
    year: str
    overview: str
    rating: float
    poster_path: Optional[str]

    @property
    def poster_url(self) -> Optional[str]:
        if self.poster_path:
            return f"{IMAGE_BASE}/w500{self.poster_path}"
        return None


def _get(path: str, **params) -> dict:
    params["api_key"] = TMDB_API_KEY
    params["language"] = params.get("language", "es-ES")
    r = httpx.get(f"{BASE}{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def search_movies(query: str, page: int = 1) -> list[Movie]:
    data = _get("/search/movie", query=query, page=page)
    results = []
    for item in data.get("results", [])[:8]:
        release = item.get("release_date", "")
        results.append(Movie(
            tmdb_id=item["id"],
            title=item.get("title", "Unknown"),
            year=release[:4] if release else "?",
            overview=item.get("overview", ""),
            rating=item.get("vote_average", 0),
            poster_path=item.get("poster_path"),
            backdrop_path=item.get("backdrop_path"),
        ))
    return results


def search_tv(query: str, page: int = 1) -> list[TVShow]:
    data = _get("/search/tv", query=query, page=page)
    results = []
    for item in data.get("results", [])[:8]:
        first_air = item.get("first_air_date", "")
        results.append(TVShow(
            tmdb_id=item["id"],
            name=item.get("name", "Unknown"),
            year=first_air[:4] if first_air else "?",
            overview=item.get("overview", ""),
            rating=item.get("vote_average", 0),
            poster_path=item.get("poster_path"),
        ))
    return results


def get_movie(tmdb_id: int) -> Movie:
    data = _get(f"/movie/{tmdb_id}")
    release = data.get("release_date", "")
    return Movie(
        tmdb_id=data["id"],
        title=data.get("title", "Unknown"),
        year=release[:4] if release else "?",
        overview=data.get("overview", ""),
        rating=data.get("vote_average", 0),
        poster_path=data.get("poster_path"),
        backdrop_path=data.get("backdrop_path"),
    )


@dataclass
class CastMember:
    tmdb_id: int
    name: str
    character: str
    profile_path: Optional[str]

    @property
    def profile_url(self) -> Optional[str]:
        if self.profile_path:
            return f"{IMAGE_BASE}/w200{self.profile_path}"
        return None


def get_movie_credits(tmdb_id: int) -> tuple[list[str], list[str]]:
    data = _get(f"/movie/{tmdb_id}/credits")
    cast = [c["name"] for c in data.get("cast", [])[:5]]
    directors = [
        c["name"]
        for c in data.get("crew", [])
        if c.get("job") == "Director"
    ]
    return cast, directors


def get_movie_cast(tmdb_id: int) -> list[CastMember]:
    data = _get(f"/movie/{tmdb_id}/credits")
    return _parse_credits(data)


def get_tv_cast(tmdb_id: int) -> list[CastMember]:
    data = _get(f"/tv/{tmdb_id}/credits")
    return _parse_credits(data)


def _parse_credits(data: dict) -> list[CastMember]:
    members = []
    for c in data.get("crew", []):
        if c.get("job") == "Director":
            members.append(CastMember(
                tmdb_id=c["id"],
                name=c.get("name", "?"),
                character="Director",
                profile_path=c.get("profile_path"),
            ))
    for c in data.get("cast", [])[:15]:
        members.append(CastMember(
            tmdb_id=c["id"],
            name=c.get("name", "?"),
            character=c.get("character", "?"),
            profile_path=c.get("profile_path"),
        ))
    return members


def get_tv_seasons(tmdb_id: int) -> list[dict]:
    data = _get(f"/tv/{tmdb_id}")
    seasons = []
    for s in data.get("seasons", []):
        if s.get("season_number", 0) > 0:
            seasons.append({
                "season_number": s["season_number"],
                "name": s.get("name", f"Season {s['season_number']}"),
                "episode_count": s.get("episode_count", 0),
                "overview": s.get("overview", ""),
            })
    return seasons


def get_tv_external_ids(tmdb_id: int) -> dict:
    return _get(f"/tv/{tmdb_id}/external_ids")


def get_person(person_id: int) -> dict:
    return _get(f"/person/{person_id}")


def get_tv(tmdb_id: int) -> TVShow:
    data = _get(f"/tv/{tmdb_id}")
    first_air = data.get("first_air_date", "")
    return TVShow(
        tmdb_id=data["id"],
        name=data.get("name", "Unknown"),
        year=first_air[:4] if first_air else "?",
        overview=data.get("overview", ""),
        rating=data.get("vote_average", 0),
        poster_path=data.get("poster_path"),
    )


def search_person(query: str) -> list[Person]:
    data = _get("/search/person", query=query)
    results = []
    for item in data.get("results", [])[:8]:
        known = item.get("known_for_department", "")
        known_for = ", ".join(
            m.get("title", m.get("name", "?"))
            for m in item.get("known_for", [])[:3]
        )
        results.append(Person(
            tmdb_id=item["id"],
            name=item.get("name", "Unknown"),
            known_for=f"{known}: {known_for}" if known_for else known,
            profile_path=item.get("profile_path"),
        ))
    return results


def get_person_movie_credits(person_id: int, page: int = 1) -> list[Movie]:
    data = _get(f"/person/{person_id}/movie_credits")
    return _parse_person_credits(data, page)


def get_person_tv_credits(person_id: int, page: int = 1) -> list[TVShow]:
    data = _get(f"/person/{person_id}/tv_credits")
    results = []
    seen: set[int] = set()
    for item in data.get("cast", []):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        first_air = item.get("first_air_date", "")
        results.append(TVShow(
            tmdb_id=item["id"],
            name=item.get("name", "Unknown"),
            year=first_air[:4] if first_air else "?",
            overview=item.get("overview", ""),
            rating=item.get("vote_average", 0),
            poster_path=item.get("poster_path"),
        ))
    results.sort(key=lambda s: s.rating, reverse=True)
    page_size = 8
    start = (page - 1) * page_size
    return results[start:start + page_size]


def _parse_person_credits(data: dict, page: int = 1) -> list[Movie]:
    results = []
    seen: set[int] = set()
    for item in data.get("cast", []):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        release = item.get("release_date", "")
        results.append(Movie(
            tmdb_id=item["id"],
            title=item.get("title", "Unknown"),
            year=release[:4] if release else "?",
            overview=item.get("overview", ""),
            rating=item.get("vote_average", 0),
            poster_path=item.get("poster_path"),
            backdrop_path=item.get("backdrop_path"),
        ))
    results.sort(key=lambda m: m.rating, reverse=True)
    page_size = 8
    start = (page - 1) * page_size
    return results[start:start + page_size]
