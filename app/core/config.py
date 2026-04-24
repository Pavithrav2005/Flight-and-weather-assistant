from pydantic import Field
from pydantic import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Flight Intelligence API"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    aviationstack_api_key: str = Field(min_length=1, validation_alias="AVIATIONSTACK_API_KEY")
    aviationstack_base_url: str = Field(default="https://api.aviationstack.com/v1", validation_alias="AVIATIONSTACK_BASE_URL")

    openweather_api_key: str = Field(min_length=1, validation_alias="OPENWEATHER_API_KEY")
    openweather_base_url: str = Field(default="https://api.openweathermap.org/data/2.5", validation_alias="OPENWEATHER_BASE_URL")

    nvidia_nim_api_key: str = Field(min_length=1, validation_alias=AliasChoices("NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"))
    nvidia_nim_model: str = Field(default="meta/llama-3.1-70b-instruct", min_length=1, validation_alias="NVIDIA_NIM_MODEL")
    nvidia_nim_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", validation_alias=AliasChoices("NVIDIA_NIM_BASE_URL", "NIM_BASE_URL"))
    nvidia_nim_timeout_seconds: float = Field(default=30.0, validation_alias="NVIDIA_NIM_TIMEOUT_SECONDS")

    external_api_timeout_seconds: float = Field(default=10.0, validation_alias="EXTERNAL_API_TIMEOUT_SECONDS")
    external_api_retries: int = Field(default=3, validation_alias="EXTERNAL_API_RETRIES")
    cache_ttl_seconds: int = Field(default=300, validation_alias="CACHE_TTL_SECONDS")


def get_settings() -> Settings:
    return Settings()
