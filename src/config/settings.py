import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    BASE_URL: str = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    LOGIN_TIME_DAYS: int = 7

    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "host")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 25))
    EMAIL_HOST_USER: str = os.getenv("EMAIL_HOST_USER", "testuser")
    EMAIL_HOST_PASSWORD: str = os.getenv("EMAIL_HOST_PASSWORD", "test_password")
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"

    PATH_TO_EMAIL_TEMPLATES_DIR: str = str(
        BASE_DIR / "src" / "notifications" / "templates"
    )
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    PASSWORD_RESET_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_RESET_COMPLETE_TEMPLATE_NAME: str = "password_reset_complete.html"

    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "test_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "test_password")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "test_host")
    POSTGRES_DB_PORT: int = int(os.getenv("POSTGRES_DB_PORT", 5432))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "test_db")

    SECRET_KEY_ACCESS: str = os.getenv("SECRET_KEY_ACCESS", os.urandom(32).hex())
    SECRET_KEY_REFRESH: str = os.getenv("SECRET_KEY_REFRESH", os.urandom(32).hex())
    JWT_SIGNING_ALGORITHM: str = os.getenv("JWT_SIGNING_ALGORITHM", "HS256")

    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    DOMAIN: str = os.getenv("DOMAIN", "127.0.0.1")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    TESTING: bool = os.getenv("TESTING", "False").lower() == "true"

    @property
    def database_url(self) -> str:
        db_name = f"{self.POSTGRES_DB}_test" if self.TESTING else self.POSTGRES_DB
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_DB_PORT}/{db_name}"
        )

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


def get_settings() -> BaseSettings:
    return settings
