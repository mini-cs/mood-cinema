import pytest
import requests

from core.models import MediaItem, TmdbError
from core.tmdb_client import TmdbClient, filter_by_genre, image_url, parse_media_item, pick_trailer


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, headers=None):
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._json


class FakeSession:
    """responses를 순서대로 돌려준다(예외면 raise). 다 쓰면 마지막 것을 반복한다."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        r = self.responses[min(len(self.calls), len(self.responses)) - 1]
        if isinstance(r, Exception):
            raise r
        return r


def _client(*responses, sleeps=None):
    session = FakeSession(*responses)
    sleep = sleeps.append if sleeps is not None else (lambda s: None)
    return TmdbClient("secret-key", session=session, sleep=sleep), session


MOVIE = {
    "id": 1, "title": "기생충", "original_title": "Parasite", "release_date": "2019-05-30",
    "vote_average": 8.5, "overview": "줄거리", "poster_path": "/p.jpg", "backdrop_path": "/b.jpg", "genre_ids": [18],
}
TV = {
    "id": 2, "name": "아케인", "original_name": "Arcane", "first_air_date": "2021-11-06",
    "vote_average": 8.7, "overview": "", "poster_path": None, "backdrop_path": None, "genre_ids": [10765, 18],
}


def test_parse_movie_and_tv_fields():
    m = parse_media_item(MOVIE, "movie")
    assert (m.tmdb_id, m.media_type, m.title, m.original_title, m.year) == (1, "movie", "기생충", "Parasite", 2019)
    assert m.genre_ids == (18,)
    t = parse_media_item({**TV, "media_type": "tv"})
    assert (t.media_type, t.title, t.original_title, t.year) == ("tv", "아케인", "Arcane", 2021)


def test_parse_handles_missing_fields():
    raw = {"id": 3, "title": "무제", "original_title": "Untitled", "release_date": "", "poster_path": None, "overview": None}
    m = parse_media_item(raw, "movie")
    assert (m.year, m.poster_path, m.overview, m.vote_average) == (None, None, "", 0.0)


def test_trending_skips_person():
    body = {"results": [{**MOVIE, "media_type": "movie"}, {"id": 9, "name": "배우", "media_type": "person"}, {**TV, "media_type": "tv"}]}
    client, session = _client(FakeResponse(json_body=body))
    items = client.trending("all", "week")
    assert [i.media_type for i in items] == ["movie", "tv"]
    assert session.calls[0]["url"].endswith("/trending/all/week")
    assert session.calls[0]["params"]["language"] == "ko-KR"


GENRE_MAP = {18: "드라마", 10765: "Sci-Fi & Fantasy", 28: "액션"}


def test_filter_by_genre_matches_movie_and_tv_by_name():
    items = [parse_media_item(MOVIE, "movie"), parse_media_item({**MOVIE, "id": 5, "genre_ids": [28]}, "movie"), parse_media_item(TV, "tv")]
    assert [i.tmdb_id for i in filter_by_genre(items, "드라마", GENRE_MAP)] == [1, 2]


def test_filter_by_genre_empty_when_no_match():
    assert filter_by_genre([parse_media_item(MOVIE, "movie")], "액션", GENRE_MAP) == []


def test_pick_trailer_rules():
    trailer = {"site": "YouTube", "type": "Trailer", "key": "T"}
    teaser = {"site": "YouTube", "type": "Teaser", "key": "S"}
    vimeo = {"site": "Vimeo", "type": "Trailer", "key": "V"}
    assert pick_trailer([teaser, vimeo, trailer]) == "T"
    assert pick_trailer([teaser]) == "S"
    assert pick_trailer([vimeo]) is None
    assert pick_trailer([]) is None


def test_genres_merges_movie_and_tv():
    client, session = _client(
        FakeResponse(json_body={"genres": [{"id": 18, "name": "드라마"}]}),
        FakeResponse(json_body={"genres": [{"id": 10765, "name": "Sci-Fi & Fantasy"}]}),
    )
    assert client.genres() == {18: "드라마", 10765: "Sci-Fi & Fantasy"}


def test_search_year_param_by_media_type():
    client, session = _client(FakeResponse(json_body={"results": [MOVIE]}))
    assert client.search("Parasite", "movie", 2019)[0].tmdb_id == 1
    client.search("Arcane", "tv", 2019)
    assert session.calls[0]["params"]["year"] == 2019
    assert session.calls[1]["params"]["first_air_date_year"] == 2019
    assert "year" not in session.calls[1]["params"]


def test_detail_parses_runtime_seasons_trailer():
    videos = {"results": [{"site": "YouTube", "type": "Trailer", "key": "abc"}]}
    movie = {**MOVIE, "runtime": 132, "genres": [{"id": 18, "name": "드라마"}], "videos": videos}
    tv = {**TV, "number_of_seasons": 3, "genres": [{"id": 18, "name": "드라마"}], "videos": {"results": []}}
    client, session = _client(FakeResponse(json_body=movie), FakeResponse(json_body=tv))

    d = client.detail(1, "movie")
    assert (d.runtime_min, d.seasons, d.trailer_key, d.genres) == (132, None, "abc", ("드라마",))
    assert d.item.title == "기생충"
    assert session.calls[0]["params"]["append_to_response"] == "videos"
    assert session.calls[0]["params"]["include_video_language"] == "ko,en"

    d = client.detail(2, "tv")
    assert (d.runtime_min, d.seasons, d.trailer_key) == (None, 3, None)


def test_image_url():
    assert image_url("/a.jpg", "w342") == "https://image.tmdb.org/t/p/w342/a.jpg"
    assert image_url(None, "w342") is None


def test_http_401_not_retried():
    client, session = _client(FakeResponse(401))
    with pytest.raises(TmdbError) as e:
        client.trending("movie", "day")
    assert e.value.status == 401
    assert len(session.calls) == 1


def test_retries_on_429_with_retry_after():
    sleeps = []
    client, session = _client(
        FakeResponse(429, headers={"Retry-After": "1"}), FakeResponse(json_body={"results": [MOVIE]}), sleeps=sleeps
    )
    assert len(client.trending("movie", "day")) == 1
    assert sleeps == [1.0]


def test_errors_never_contain_api_key():
    client, session = _client(requests.ConnectionError("https://api.themoviedb.org/3/x?api_key=secret-key"))
    with pytest.raises(TmdbError) as e:
        client.trending("movie", "day")
    err = e.value
    assert "secret-key" not in str(err)
    assert err.__cause__ is None
    assert err.__suppress_context__ is True
    assert len(session.calls) == 4
