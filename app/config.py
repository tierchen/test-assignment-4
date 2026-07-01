from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="local/etc/.env", env_file_encoding="utf-8")

    database_url: str
    rabbitmq_url: str
    queue_name: str
    queue_max_priority: int
    worker_concurrency: int


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
