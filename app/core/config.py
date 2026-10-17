from pathlib import Path

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
  model_config = SettingsConfigDict(
    env_file=BACKEND_ROOT / '.env',
    env_file_encoding='utf-8',
    extra='ignore',
    str_strip_whitespace=True,
  )

  # Application
  app_name: str = Field(min_length=1)
  app_debug: bool

  # Database
  db_host: str = Field(min_length=1)
  db_port: int = Field(ge=1, le=65535)
  db_user: str = Field(min_length=1, validation_alias='POSTGRES_USER')
  db_password: SecretStr = Field(
    min_length=1,
    validation_alias='POSTGRES_PASSWORD',
  )
  db_name: str = Field(min_length=1, validation_alias='POSTGRES_DB')

  # Authentication and tokens
  jwt_secret_key: SecretStr = Field(min_length=32)
  jwt_issuer: str = Field(min_length=1)
  jwt_audience: str = Field(min_length=1)
  access_token_expire_minutes: int = Field(ge=1)
  refresh_token_expire_days: int = Field(ge=1)

  # Email verification
  email_verification_token_expire_minutes: int = Field(ge=1)
  email_verification_resend_cooldown_seconds: int = Field(ge=0)
  email_verification_url: AnyHttpUrl

  # SMTP
  smtp_host: str = Field(min_length=1)
  smtp_port: int = Field(ge=1, le=65535)
  smtp_username: str | None
  smtp_password: SecretStr | None
  smtp_use_tls: bool
  smtp_start_tls: bool
  smtp_timeout_seconds: float = Field(gt=0)
  smtp_from_email: EmailStr
  smtp_from_name: str = Field(min_length=1)

  @property
  def database_url(self) -> URL:
    return URL.create(
      drivername='postgresql+asyncpg',
      username=self.db_user,
      password=self.db_password.get_secret_value(),
      host=self.db_host,
      port=self.db_port,
      database=self.db_name,
    )

  @model_validator(mode='after')
  def validate_auth_configuration(self) -> Settings:
    if self.jwt_secret_key.get_secret_value().startswith('replace-this-'):
      raise ValueError(
        'Replace the example JWT_SECRET_KEY before starting the app'
      )
    has_smtp_username = bool(self.smtp_username)
    has_smtp_password = (
      self.smtp_password is not None
      and bool(self.smtp_password.get_secret_value())
    )
    if has_smtp_username != has_smtp_password:
      raise ValueError(
        'SMTP_USERNAME and SMTP_PASSWORD must be configured together'
      )
    if self.smtp_use_tls and self.smtp_start_tls:
      raise ValueError('SMTP_USE_TLS and SMTP_START_TLS are mutually exclusive')
    return self


settings = Settings()
