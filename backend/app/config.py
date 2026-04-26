from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic Claude API (optional — for future use)
    anthropic_api_key: str = ""

    # Google Gemini API (active AI provider)
    gemini_api_key: str

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:5173/auth/callback"

    # Firebase
    firebase_project_id: str
    firebase_service_account_json: str

    # CORS — comma-separated string, split into list via property
    allowed_origins: str = "http://localhost:5173"

    # Rate limiting
    sync_cooldown_seconds: int = 300  # 5 minutes
    sync_max_burst: int = 2  # Allow 2 rapid syncs before cooldown

    @property
    def cors_origins(self) -> list[str]:
        """Split comma-separated ALLOWED_ORIGINS into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()

