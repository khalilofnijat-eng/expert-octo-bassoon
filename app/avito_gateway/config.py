"""Gateway configuration.

Credentials come from ``app.config.Settings`` (``AVITO_CLIENT_ID``, ``AVITO_CLIENT_SECRET``, both
``SecretStr``; BLOCKERS B-011). Tunables come from ``AVITO_GATEWAY_*`` environment variables or
``.env``; every default below that is not documented by Avito is a conservative choice of ours and
is marked UNVERIFIED with the T-010 item that should settle it.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.avito_gateway.errors import MissingCredentialsError
from app.config import Settings, get_settings

DEFAULT_BASE_URL = "https://api.avito.ru"


@dataclass(frozen=True, repr=False)
class Credentials:
    """``client_credentials`` pair. Its repr never shows the values."""

    client_id: SecretStr
    client_secret: SecretStr

    def __repr__(self) -> str:
        return "Credentials(client_id=**********, client_secret=**********)"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Credentials:
        settings = settings if settings is not None else get_settings()
        missing = [
            name
            for name, value in (
                ("AVITO_CLIENT_ID", settings.avito_client_id),
                ("AVITO_CLIENT_SECRET", settings.avito_client_secret),
            )
            if value is None or not value.get_secret_value()
        ]
        if missing or settings.avito_client_id is None or settings.avito_client_secret is None:
            raise MissingCredentialsError(f"not configured: {', '.join(missing)}")
        return cls(settings.avito_client_id, settings.avito_client_secret)


class RateLimit(BaseModel):
    """One token bucket: ``per_minute`` sustained rate, ``burst`` bucket size."""

    per_minute: float = Field(gt=0)
    burst: int = Field(default=1, ge=1)


# Items limits are in the spec copy (INTEGRATIONS §3.1: items list 25/min, item detail 500/min).
# Messenger, token and accounts/self limits are NOT documented: UNVERIFIED (T-010 records request
# counts and any 429 it meets); the values are deliberately conservative.
DEFAULT_RATE_LIMITS: dict[str, RateLimit] = {
    "token": RateLimit(per_minute=6, burst=2),  # UNVERIFIED
    "accounts_self": RateLimit(per_minute=30, burst=2),  # UNVERIFIED
    "chats_list": RateLimit(per_minute=30, burst=3),  # UNVERIFIED (T-010 M1)
    "chat_detail": RateLimit(per_minute=30, burst=3),  # UNVERIFIED (T-010 M9)
    "messages_list": RateLimit(per_minute=30, burst=3),  # UNVERIFIED (T-010 M2, M8)
    "voice_files": RateLimit(per_minute=10, burst=1),  # UNVERIFIED (T-010 M8)
    "items_list": RateLimit(per_minute=25, burst=5),  # spec copy: 25/min; burst UNVERIFIED
    "item_detail": RateLimit(per_minute=500, burst=10),  # spec copy: 500/min; burst UNVERIFIED
    # Sending (T-018): limit not documented, UNVERIFIED; one message every 3 s at most.
    "send_text": RateLimit(per_minute=20, burst=1),
}


class GatewayConfig(BaseSettings):
    """Non-secret gateway tunables (env prefix ``AVITO_GATEWAY_``)."""

    model_config = SettingsConfigDict(
        env_prefix="AVITO_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    base_url: str = DEFAULT_BASE_URL
    # Plain http is refused unless explicitly allowed (only for a local mock server).
    allow_insecure_http: bool = False

    connect_timeout_s: float = Field(default=5.0, gt=0)
    read_timeout_s: float = Field(default=20.0, gt=0)
    write_timeout_s: float = Field(default=10.0, gt=0)
    pool_timeout_s: float = Field(default=5.0, gt=0)

    # The token is renewed when less than this is left of ``expires_in`` (ARCHITECTURE §6.9).
    # For very short lifetimes the margin is capped at half the lifetime.
    token_safety_margin_s: float = Field(default=300.0, ge=0)
    # After a 401 on a read: refresh the token once and repeat the request once (ARCHITECTURE
    # §6.9). The T-010 measurement script must stop on the first 401 instead (T-010 brief), so it
    # sets this to False.
    refresh_on_401: bool = True
    # Used only if the token reply lacks ``expires_in`` (UNVERIFIED; spec example: 3600).
    token_ttl_fallback_s: float = Field(default=3600.0, gt=0)

    rate_limits: dict[str, RateLimit] = Field(default_factory=lambda: dict(DEFAULT_RATE_LIMITS))
    # Bucket for an endpoint missing from ``rate_limits``.
    default_rate_limit: RateLimit = RateLimit(per_minute=30, burst=1)
    # Longest share of a bucket that ``bulk`` traffic may use (ARCHITECTURE §6.10).
    bulk_share: float = Field(default=0.5, gt=0, le=1)
    # After a 429 without a usable Retry-After, both classes pause this long (UNVERIFIED whether
    # Avito sends Retry-After at all). Retry-After values are capped at ``max_retry_after_s``.
    default_429_cooldown_s: float = Field(default=60.0, ge=0)
    max_retry_after_s: float = Field(default=900.0, gt=0)

    # Messenger ``limit``: spec copy says "<100" but its schema says max 100 → we use ≤ 99
    # (INTEGRATIONS §3.1). Default page size 50 (T-010 brief).
    page_limit_default: int = Field(default=50, ge=1)
    page_limit_max: int = Field(default=99, ge=1, le=100)
    # Messenger ``offset``: the spec copy's schema gives maximum 1000. UNVERIFIED (T-010 M8): if
    # it holds, one listing cannot reach beyond offset 1000; pagination stops there with reason
    # ``offset_cap`` instead of sending an out-of-range request.
    offset_max: int = Field(default=1000, ge=0)

    @field_validator("base_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _check_scheme(self) -> GatewayConfig:
        parts = urlsplit(self.base_url)
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise ValueError("AVITO_GATEWAY_BASE_URL must be an absolute http(s) URL")
        if parts.scheme == "http" and not self.allow_insecure_http:
            raise ValueError("plain http base URL requires AVITO_GATEWAY_ALLOW_INSECURE_HTTP=true")
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError("AVITO_GATEWAY_BASE_URL must not contain a path, query or fragment")
        if self.page_limit_default > self.page_limit_max:
            raise ValueError("page_limit_default must not exceed page_limit_max")
        return self

    def rate_limit_for(self, endpoint: str) -> RateLimit:
        return self.rate_limits.get(endpoint, self.default_rate_limit)
