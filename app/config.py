from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    stripe_webhook_secret: str = ""
    github_webhook_secret: str = ""
    slack_signing_secret: str = ""

    # Upstash Redis REST API (HTTP — no TCP credentials needed)
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    supabase_url: str = ""
    supabase_service_key: str = ""

    anthropic_api_key: str = ""


settings = Settings()
