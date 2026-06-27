from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = repo root (one level above the app/ package).
ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App configuration, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    tesco_email: str = ""
    tesco_password: str = ""

    pdf_path: str = "recipes.pdf"
    db_path: str = "mealplanner.db"
    tesco_storage_state: str = "tesco_state.json"

    # Extraction tuning.
    extraction_model: str = "claude-opus-4-8"
    rasterize_max_px: int = 1600  # longest edge of each rendered page image
    extraction_batch_size: int = 4  # pages per Claude request
    extraction_overlap: int = 1  # shared pages between consecutive batches

    def resolve(self, value: str) -> Path:
        """Resolve a possibly-relative config path against the project root."""
        p = Path(value)
        return p if p.is_absolute() else ROOT / p


settings = Settings()
