from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Kaori AI"
    smtp_tls: bool = True
    frontend_url: str = "http://localhost:3000"
    max_retries: int = 3
    retry_wait_seconds: float = 2.0

    # Issue #6 outbox — see services/notification-service/outbox_poller.py
    # for how these wire together. DATABASE_URL targets the same Postgres
    # the rest of the platform uses; the poller asks for SELECT/UPDATE on
    # notification_outbox (no DDL — auth-service's Flyway owns the table).
    database_url: str = (
        "postgresql://kaori_app:kaori_app_password@postgres:5432/kaori"
    )
    outbox_poll_enabled: bool = True
    outbox_poll_interval_seconds: float = 5.0
    outbox_batch_size: int = 10

    class Config:
        env_file = ".env"
        env_prefix = ""
        # Env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
        # FRONTEND_URL, DATABASE_URL, OUTBOX_POLL_*


@lru_cache
def get_settings() -> Settings:
    return Settings()
