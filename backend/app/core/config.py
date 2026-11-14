"""Application settings.

Loaded from ``backend/.env_{VIP_ENV}`` (``dev`` by default) and from the process environment.
Every key is prefixed ``VIP_`` so the process can live next to WeOS, BR Licitar and AIDeed
without reading their variables. Never read a file named ``.env`` (that is WeOS's).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


def _env_file() -> Path:
    return BASE_DIR / f".env_{os.getenv('VIP_ENV', 'dev')}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIP_",
        env_file=_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "dev"
    port: int = 3399
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://vip:vip@localhost:5439/vip"
    redis_url: str = "redis://localhost:6382/0"

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 14
    cookie_secure: bool = False
    refresh_cookie_name: str = "vip_refresh"

    cors_origins: str = "http://localhost:3400"
    frontend_url: str = "http://localhost:3400"

    # Outgoing e-mail (app/core/mail.py). provider "smtp" = the mail server; empty = log only.
    # security: ssl (465) | starttls (587) | none
    email_provider: str = ""
    email_from: str = "VIP Network <nao-responda@vipnetwork.com.br>"
    email_reply_to: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 465
    email_smtp_security: str = "ssl"
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_timeout_seconds: int = 20
    # every e-mail together, per hour and per day (Admin › E-mails › Configuração can lower it)
    mail_hourly_cap: int = 500
    mail_daily_cap: int = 5000

    # Stripe (docs/PLANO_TECNICO.md §1). Empty key outside production = no real charge: the
    # subscription is created locally in the state Stripe would answer (dev, tests).
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_monthly: str = ""  # recurring R$ 250/month
    stripe_price_annual: str = ""  # recurring R$ 2.500/year
    trial_hours: int = 168

    # CNPJ lookup, same chain as BR Licitar: the AIware Receita base, then the public CNPJá API.
    cnpj_providers: str = "aiware,cnpja"
    market_database_url: str = ""  # optional direct read of the AIware Receita base
    aiware_api_url: str = ""  # route /api/v1/sdr/market/company
    aiware_api_token: str = ""

    # WeOS public API V2 (agents). Empty token = the local matching fallback.
    weos_api_url: str = "https://api-weos.wegen-ai.com/api/v2/public"
    weos_api_token: str = ""
    weos_workspace_id: str = ""

    fernet_key: str = ""

    # Object storage (MinIO / S3): bucket "vip", keys <company-slug>/<kind>/<file>. Empty endpoint =
    # files on local disk under upload_dir (tests, machines without MinIO).
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "vip"
    s3_region: str = "us-east-1"

    # local fallback for files (empty = backend/data/uploads)
    upload_dir: str = ""
    upload_max_mb: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def stripe_live(self) -> bool:
        return bool(self.stripe_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
