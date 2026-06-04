from discord_bot.spotify import parse_spotify, is_spotify_url, _fmt
from discord_bot.playlists import PlaylistStore
from discord_bot.cogs.music import _youtube_id
from discord_bot.main import CombinedBot, INITIAL_COGS


def test_spotify_parse():
    assert is_spotify_url("https://open.spotify.com/track/abc123")
    assert is_spotify_url("spotify:playlist:xyz")
    assert not is_spotify_url("https://youtube.com/watch?v=x")
    assert parse_spotify("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT") == (
        "track",
        "4cOdK2wGLETKBW3PvgPWqT",
    )
    assert parse_spotify("https://open.spotify.com/intl-de/album/1A2B3c")[0] == "album"
    assert parse_spotify("spotify:playlist:37i9dQ") == ("playlist", "37i9dQ")
    assert parse_spotify("not a spotify link") == (None, None)


def test_spotify_fmt():
    t = {"name": "Song", "artists": [{"name": "A"}, {"name": "B"}]}
    assert _fmt(t) == "A, B - Song"


def test_youtube_id():
    assert _youtube_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _youtube_id("ytsearch1:foo bar") is None


def test_playlist_store(tmp_path):
    s = PlaylistStore(tmp_path / "pl.json")
    assert s.names(1) == {}
    n = s.save(
        1,
        "chill",
        [{"title": "A", "url": "u1"}, {"title": "B", "url": "u2"}, {"title": "x", "url": None}],
    )
    assert n == 2  # трек без url пропускається
    assert s.names(1) == {"chill": 2}
    assert len(s.get(1, "chill")) == 2
    assert PlaylistStore(tmp_path / "pl.json").names(1) == {"chill": 2}  # персист
    assert s.delete(1, "chill") is True
    assert s.delete(1, "nope") is False
    assert s.get(1, "chill") is None


async def test_phase2_commands():
    bot = CombinedBot()
    for ext in INITIAL_COGS:
        await bot.load_extension(ext)
    names = {c.name for c in bot.commands}
    for expected in ["search", "playlist", "autoplay"]:
        assert expected in names, f"missing {expected}"
    # підкоманди плейлиста
    pl = bot.get_command("playlist")
    subs = {c.name for c in pl.commands}
    assert {"save", "load", "list", "show", "delete"} <= subs, subs
    await bot.close()
