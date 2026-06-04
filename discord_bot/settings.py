"""Пер-серверні налаштування у JSON (патерн FavoritesStore).

Фундамент для динамічного префікса, автоплею, DJ-ролі тощо.
Використовуй глобальний екземпляр `settings`.
"""
import json
import logging

from discord_bot import config

log = logging.getLogger("bot.settings")

SETTINGS_FILE = config.DATA_DIR / "guild_settings.json"

# Значення за замовчуванням (беруться з .env, де доречно)
DEFAULTS = {
    "prefix": config.COMMAND_PREFIX,
    "default_filter": config.DEFAULT_FILTER,
    "dj_role_id": None,
    "autoplay": False,
}


class GuildSettingsStore:
    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self.data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            log.exception("Не вдалося прочитати %s", self.path)
        return {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            log.exception("Не вдалося зберегти налаштування")

    def get(self, guild_id, key: str):
        """Значення налаштування для сервера (або дефолт)."""
        g = self.data.get(str(guild_id), {})
        return g.get(key, DEFAULTS.get(key))

    def set(self, guild_id, key: str, value):
        self.data.setdefault(str(guild_id), {})[key] = value
        self._save()

    def all(self, guild_id) -> dict:
        merged = dict(DEFAULTS)
        merged.update(self.data.get(str(guild_id), {}))
        return merged


# Глобальний екземпляр для cogs і динамічного префікса
settings = GuildSettingsStore()
