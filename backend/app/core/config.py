"""Runtime settings, read from environment variables (see .env.example)."""
import os


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self):
        self.APP_NAME = "TradeBot"
        self.ENV = os.getenv("ENV", "development")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tradebot.db")
        self.JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production-please")
        self.ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
        self.REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
        self.RESET_TOKEN_MINUTES = int(os.getenv("RESET_TOKEN_MINUTES", "30"))
        self.CORS_ORIGINS = [o.strip() for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o.strip()]
        self.FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
        # Practice market
        self.ENABLE_SIMULATOR = _bool("ENABLE_SIMULATOR", True)
        self.TICK_SECONDS = float(os.getenv("TICK_SECONDS", "1.0"))
        self.TICKS_PER_BAR = int(os.getenv("TICKS_PER_BAR", "30"))
        self.SEED_DEMO = _bool("SEED_DEMO", True)
        self.HISTORY_BARS = int(os.getenv("HISTORY_BARS", "600"))
        self.STARTING_CASH = float(os.getenv("STARTING_CASH", "1000000"))
        # Bot sandbox
        self.BOT_TIMEOUT_S = float(os.getenv("BOT_TIMEOUT_S", "10"))
        self.BOT_CPU_S = int(os.getenv("BOT_CPU_S", "10"))
        self.BOT_MEMORY_MB = int(os.getenv("BOT_MEMORY_MB", "1024"))
        self.BOT_HISTORY_BARS = int(os.getenv("BOT_HISTORY_BARS", "400"))

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
