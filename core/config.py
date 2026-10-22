import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.models import ConfigError


@dataclass(frozen=True)
class Settings:
    tmdb_api_key: str | None
    gemini_api_key: str | None
    gemini_model: str
    gemini_rpm_limit: int
    gemini_daily_limit: int
    recommend_cooldown_sec: int

    def missing_keys(self) -> list[str]:
        keys = [("TMDB_API_KEY", self.tmdb_api_key), ("GEMINI_API_KEY", self.gemini_api_key)]
        return [name for name, value in keys if not value]


def load_settings(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    secrets = secrets or {}
    environ = os.environ if environ is None else environ

    def get(name: str, default: Any = None) -> Any:
        for source in (secrets, environ):
            value = source.get(name)
            if value is not None and value != "":
                return value
        return default

    def get_int(name: str, default: int, minimum: int) -> int:
        value = get(name, default)
        try:
            # str() 거쳐서 TOML의 7.5·true 같은 값이 조용히 정수로 바뀌지 않게 한다
            number = int(str(value))
        except ValueError:
            raise ConfigError(f"{name}은(는) 정수여야 합니다.") from None
        if number < minimum:
            raise ConfigError(f"{name}은(는) {minimum} 이상이어야 합니다.")
        return number

    return Settings(
        tmdb_api_key=get("TMDB_API_KEY"),
        gemini_api_key=get("GEMINI_API_KEY"),
        gemini_model=get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        gemini_rpm_limit=get_int("GEMINI_RPM_LIMIT", 5, 1),
        gemini_daily_limit=get_int("GEMINI_DAILY_LIMIT", 200, 1),
        recommend_cooldown_sec=get_int("RECOMMEND_COOLDOWN_SEC", 10, 0),
    )
