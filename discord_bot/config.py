"""Конфігурація бота: завантаження секретів і налаштувань з .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# .env лежить у корені проєкту
load_dotenv(PROJECT_ROOT / ".env")

def _int_env(name: str, default: int = 0) -> int:
    """Безпечно парсить ціле з env (не падає на сміттєвому значенні)."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GUILD_ID = _int_env("GUILD_ID", 0)
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!").strip() or "!"

# Музика
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt").strip()
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER", "").strip() or None
# Фільтр за замовчуванням для нових плеєрів (off/normalize/bassboost/...)
DEFAULT_FILTER = os.getenv("DEFAULT_FILTER", "normalize").strip().lower() or "off"

# Spotify Web API (безкоштовно: https://developer.spotify.com/dashboard)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()

# Веб-дашборд (вмикається лише якщо задано пароль)
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1").strip() or "127.0.0.1"
DASHBOARD_PORT = _int_env("DASHBOARD_PORT", 8765)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()

# Шлях для cookies рахуємо відносно кореня проєкту, якщо вказано відносний
if COOKIES_FILE and not os.path.isabs(COOKIES_FILE):
    COOKIES_FILE = str(PROJECT_ROOT / COOKIES_FILE)


def validate() -> list[str]:
    """Повертає список фатальних проблем конфігурації (порожній = все ок)."""
    problems = []
    if not TOKEN or TOKEN == "your_token_here":
        problems.append(
            "DISCORD_BOT_TOKEN не встановлено. Скопіюй .env.example у .env і встав токен "
            "(Developer Portal → Bot → Reset Token)."
        )
    raw_guild = os.getenv("GUILD_ID", "").strip()
    if raw_guild and not raw_guild.isdigit():
        problems.append(f"GUILD_ID має бути числом, а не '{raw_guild}'.")
    return problems
