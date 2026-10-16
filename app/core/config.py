from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
  model_config = SettingsConfigDict(
    env_file=BACKEND_ROOT / '.env',
    env_file_encoding='utf-8',
    extra='ignore',
    str_strip_whitespace=True,
  )

  app_name: str = Field(min_length=1)
  app_debug: bool = False


settings = Settings()
