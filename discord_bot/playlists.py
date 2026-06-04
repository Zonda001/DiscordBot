"""Іменовані плейлисти користувачів у JSON (патерн FavoritesStore).

Структура: {user_id: {name: [{title, url}, ...]}}
"""
import json
import logging

from discord_bot import config

log = logging.getLogger("bot.playlists")

PLAYLISTS_FILE = config.DATA_DIR / "playlists.json"


class PlaylistStore:
    def __init__(self, path=PLAYLISTS_FILE):
        self.path = path
        self.data: dict[str, dict[str, list]] = self._load()

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
            log.exception("Не вдалося зберегти плейлисти")

    def names(self, user_id) -> dict[str, int]:
        """{назва: к-ть треків} для користувача."""
        return {name: len(tracks) for name, tracks in self.data.get(str(user_id), {}).items()}

    def get(self, user_id, name: str):
        return self.data.get(str(user_id), {}).get(name)

    def save(self, user_id, name: str, tracks: list[dict]) -> int:
        clean = [{"title": t.get("title", "?"), "url": t.get("url")} for t in tracks if t.get("url")]
        self.data.setdefault(str(user_id), {})[name] = clean
        self._save()
        return len(clean)

    def delete(self, user_id, name: str) -> bool:
        user = self.data.get(str(user_id), {})
        if name in user:
            del user[name]
            self._save()
            return True
        return False
