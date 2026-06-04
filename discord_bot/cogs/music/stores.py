"""Сховище обраного (per-user) для музичного cog."""
import json
import logging

log = logging.getLogger("bot.music")

class FavoritesStore:
    """Персональне обране кожного користувача у JSON: {user_id: [{title,url}]}."""

    def __init__(self, path):
        self.path = path
        self.data: dict[str, list[dict]] = self._load()

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
            log.exception("Не вдалося зберегти обране")

    def get(self, user_id) -> list[dict]:
        return self.data.get(str(user_id), [])

    def add(self, user_id, track: dict) -> bool:
        items = self.data.setdefault(str(user_id), [])
        if any(t["url"] == track.get("url") for t in items):
            return False  # вже є
        items.append({"title": track.get("title", "?"), "url": track.get("url")})
        self._save()
        return True

    def remove(self, user_id, index: int):
        items = self.data.get(str(user_id), [])
        if 1 <= index <= len(items):
            removed = items.pop(index - 1)
            self._save()
            return removed
        return None
