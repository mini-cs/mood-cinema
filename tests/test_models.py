import pytest
from pydantic import ValidationError

from core.models import Recommendation, RecommendationList


def _rec(**overrides):
    data = {"title_ko": "제목", "original_title": "Title", "year": 2020, "media_type": "movie", "reason": "이유"}
    return {**data, **overrides}


def test_recommendation_list_rejects_more_than_five():
    with pytest.raises(ValidationError):
        RecommendationList(items=[_rec() for _ in range(6)])


def test_media_type_must_be_movie_or_tv():
    with pytest.raises(ValidationError):
        Recommendation(**_rec(media_type="anime"))


def test_schema_pins_limits():
    s = RecommendationList.model_json_schema()
    assert s["properties"]["items"]["maxItems"] == 5
    assert s["properties"]["items"]["minItems"] == 1
