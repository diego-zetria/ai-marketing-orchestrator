from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str = ""
    telegram_allowed_user_ids: list[int] | str = []

    # OpenRouter
    openrouter_api_key: str
    openrouter_model_id: str = "anthropic/claude-sonnet-4"

    # ClickUp
    clickup_api_token: str
    clickup_default_list_id: str
    clickup_team_id: str = ""
    clickup_webhook_secret: str = ""
    clickup_bot_user_id: str = ""
    clickup_alteration_count_field_id: str = ""
    clickup_drive_link_field_id: str = ""

    # Automation
    auto_status_mode: str = "confirm"  # "auto" or "confirm"
    auto_assign_enabled: bool = True

    # EventBridge (approval portal trigger)
    eventbridge_bus_name: str = ""  # e.g. "approval-events"
    aws_region: str = "us-east-1"

    # Telegram notifications
    telegram_notification_group_id: int = 0

    # Summary schedule
    summary_daily_hour: int = 8
    summary_daily_minute: int = 0
    summary_timezone: str = "America/Sao_Paulo"

    # Deadline alerts
    deadline_alert_hours: list[int] = [9, 14]
    deadline_alert_debounce_hours: int = 6

    # Monthly reports
    report_day_of_month: int = 1  # Day to generate reports (1 = first)
    report_hour: int = 7  # Hour in BRT (7am)

    # Instagram / Meta Graph API
    meta_app_id: str = ""
    meta_app_secret: str = ""
    instagram_sync_hours: list[int] = [6, 12, 18, 0]
    instagram_account_sync_hour: int = 7

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/marketing_bot"

    # Admin
    admin_password: str = "changeme"
    admin_jwt_secret: str = "changeme-secret"

    # STT (Speech-to-Text)
    groq_api_key: str = ""
    openai_api_key: str = ""
    audio_max_duration: int = 300

    # App
    app_env: str = "development"
    app_log_level: str = "INFO"

    # Rules engine
    rules_engine_mode: str = "yaml"  # "yaml" | "db"

    # S3 / Knowledge Base
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_endpoint_url: str = ""  # for localstack/minio in dev

    # Observability (Langfuse v3)
    observability_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    observability_service_name: str = "marketing-briefing-bot"
    observability_sample_rate: float = 1.0
    observability_sanitize_pii: bool = True

    # LLM Cost Tracking
    llm_budget_daily_usd: float = 50.0
    llm_budget_alert_threshold: float = 0.8
    llm_budget_hard_limit: bool = False

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v):
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [int(uid.strip()) for uid in v.split(",") if uid.strip()]
        return v

    @field_validator("deadline_alert_hours", mode="before")
    @classmethod
    def parse_alert_hours(cls, v):
        if isinstance(v, str):
            return [int(h.strip()) for h in v.split(",") if h.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("instagram_sync_hours", mode="before")
    @classmethod
    def parse_sync_hours(cls, v):
        if isinstance(v, str):
            return [int(h.strip()) for h in v.split(",") if h.strip()]
        if isinstance(v, int):
            return [v]
        return v
