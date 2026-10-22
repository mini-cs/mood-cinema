import pytest

from core.config import load_settings
from core.models import ConfigError


def test_secrets_override_environ():
    s = load_settings({"TMDB_API_KEY": "s"}, {"TMDB_API_KEY": "e"})
    assert s.tmdb_api_key == "s"


def test_defaults_and_missing_keys():
    s = load_settings({}, {})
    assert (s.gemini_model, s.gemini_rpm_limit, s.gemini_daily_limit, s.recommend_cooldown_sec) == ("gemini-3.5-flash-lite", 5, 200, 10)
    assert s.missing_keys() == ["TMDB_API_KEY", "GEMINI_API_KEY"]


def test_numbers_from_toml_int_and_env_str():
    assert load_settings({"GEMINI_RPM_LIMIT": 7}, {}).gemini_rpm_limit == 7
    assert load_settings({}, {"GEMINI_RPM_LIMIT": "8"}).gemini_rpm_limit == 8


@pytest.mark.parametrize("bad", ["abc", "0", "-1"])
def test_invalid_rpm_raises(bad):
    with pytest.raises(ConfigError):
        load_settings({}, {"GEMINI_RPM_LIMIT": bad})


def test_empty_key_counts_as_missing():
    assert load_settings({"TMDB_API_KEY": ""}, {}).missing_keys()[0] == "TMDB_API_KEY"
