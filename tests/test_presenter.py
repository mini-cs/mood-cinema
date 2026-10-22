from core.models import MediaDetail, MediaItem, Recommendation, RecommendedItem
from core.presenter import (
    NO_OVERVIEW,
    card_key,
    detail_view,
    genre_names,
    hero_view,
    meta_line,
    recommended_cards,
    trending_cards,
)

GENRES = {18: "드라마", 53: "스릴러", 35: "코미디"}


def _media(tmdb_id=1, media_type="movie", title="기생충", original="기생충", poster="/p.jpg", backdrop="/b.jpg", genre_ids=(18, 53)):
    return MediaItem(tmdb_id, media_type, title, original, 2019, 8.53, "줄거리", poster, backdrop, genre_ids)


def _rec(title_ko="기생충", reason="이유"):
    return Recommendation(title_ko=title_ko, original_title="Parasite", year=2019, media_type="movie", reason=reason)


def test_meta_line_formats():
    assert meta_line(2019, 8.53, genres=["드라마", "스릴러", "코미디"]) == "드라마 · 스릴러 · 2019 · ★8.5"
    assert meta_line(None, 7.0) == "★7.0"
    assert meta_line(2020, 6.0, extra=["132분"]) == "2020 · 132분 · ★6.0"


def test_genre_names_max_two_in_order():
    assert genre_names(_media(genre_ids=(35, 99, 18, 53)), GENRES) == ["코미디", "드라마"]


def test_card_key():
    assert card_key("day", _media(7, "tv")) == "day-tv-7"


def test_trending_cards_rank_and_limit():
    items = [_media(i) for i in range(1, 13)]
    ranked = trending_cards(items, "day", ranked=True)
    assert [c.rank for c in ranked] == list(range(1, 11))
    assert all(c.rank == 0 for c in trending_cards(items, "genre", ranked=False))
    first = ranked[0]
    assert (first.key, first.meta, first.clickable, first.reason) == ("day-movie-1", "2019 · ★8.5", True, "")
    assert first.poster_url == "https://image.tmdb.org/t/p/w342/p.jpg"
    assert trending_cards([_media(poster=None)], "day", ranked=True)[0].poster_url == ""


def test_recommended_card_unmatched():
    matched, unmatched = recommended_cards(
        [RecommendedItem(_rec(), _media(title="기생충 (TMDB)")), RecommendedItem(_rec("없는 영화", "이유2"), None)]
    )
    assert (matched.title, matched.reason, matched.clickable, matched.key) == ("기생충 (TMDB)", "이유", True, "rec-movie-1")
    assert (unmatched.title, unmatched.reason, unmatched.clickable) == ("없는 영화", "이유2", False)
    assert (unmatched.poster_url, unmatched.meta) == ("", "")
    assert unmatched.key and unmatched.key != matched.key


def test_hero_view_image_fallback():
    hero = hero_view(RecommendedItem(_rec(), _media()), GENRES)
    assert hero.backdrop_url == "https://image.tmdb.org/t/p/w1280/b.jpg"
    assert (hero.title, hero.meta, hero.reason) == ("기생충", "드라마 · 스릴러 · 2019 · ★8.5", "이유")
    assert hero_view(RecommendedItem(_rec(), _media(backdrop=None)), GENRES).backdrop_url == "https://image.tmdb.org/t/p/w780/p.jpg"
    assert hero_view(RecommendedItem(_rec(), _media(backdrop=None, poster=None)), GENRES).backdrop_url == ""


def test_detail_view_movie_and_tv():
    movie = detail_view(MediaDetail(_media(), ("드라마", "스릴러", "코미디"), 132, None, None))
    assert movie.meta == "드라마 · 스릴러 · 2019 · 132분 · ★8.5"
    tv = detail_view(MediaDetail(_media(media_type="tv"), ("드라마",), None, 3, None))
    assert tv.meta == "드라마 · 2019 · 시즌 3개 · ★8.5"
    assert (movie.poster_url, movie.backdrop_url) == ("https://image.tmdb.org/t/p/w342/p.jpg", "https://image.tmdb.org/t/p/w1280/b.jpg")


def test_detail_view_trailer_and_overview():
    with_trailer = detail_view(MediaDetail(_media(), (), 132, None, "abc"), reason="이유")
    assert with_trailer.trailer_embed_url == "https://www.youtube.com/embed/abc"
    assert with_trailer.reason == "이유"
    item = MediaItem(1, "movie", "기생충", "기생충", 2019, 8.5, "", None, None, ())
    empty = detail_view(MediaDetail(item, (), None, None, None))
    assert (empty.trailer_embed_url, empty.overview, empty.reason) == ("", NO_OVERVIEW, "")
    assert (empty.poster_url, empty.backdrop_url) == ("", "")


def test_detail_view_hides_same_original_title():
    assert detail_view(MediaDetail(_media(), (), None, None, None)).original_title == ""
    assert detail_view(MediaDetail(_media(original="Parasite"), (), None, None, None)).original_title == "Parasite"
