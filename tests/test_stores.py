from discord_bot.cogs.music import FavoritesStore
from discord_bot.settings import GuildSettingsStore, DEFAULTS


def test_favorites(tmp_path):
    s = FavoritesStore(tmp_path / "f.json")
    assert s.add(1, {"title": "A", "url": "u1"}) is True
    assert s.add(1, {"title": "A", "url": "u1"}) is False  # дубль
    assert s.add(1, {"title": "B", "url": "u2"}) is True
    assert len(s.get(1)) == 2
    # персистентність
    assert len(FavoritesStore(tmp_path / "f.json").get(1)) == 2
    assert s.remove(1, 1)["title"] == "A"
    assert s.remove(1, 99) is None
    assert len(s.get(1)) == 1


def test_guild_settings(tmp_path):
    s = GuildSettingsStore(tmp_path / "g.json")
    assert s.get(10, "prefix") == DEFAULTS["prefix"]
    assert s.get(10, "autoplay") is False
    s.set(10, "prefix", "?")
    s.set(10, "autoplay", True)
    # персистентність + ізоляція серверів
    s2 = GuildSettingsStore(tmp_path / "g.json")
    assert s2.get(10, "prefix") == "?"
    assert s2.get(10, "autoplay") is True
    assert s2.get(999, "prefix") == DEFAULTS["prefix"]
    assert s2.all(10)["dj_role_id"] == DEFAULTS["dj_role_id"]
