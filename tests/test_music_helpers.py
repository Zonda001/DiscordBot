from discord_bot.cogs.music import (
    fmt_time,
    progress_bar,
    build_queue_embed,
    MusicCog,
)

KNOB = "\U0001f518"  # 🔘


def test_fmt_time():
    assert fmt_time(5) == "00:05"
    assert fmt_time(75) == "01:15"
    assert fmt_time(3725) == "1:02:05"


def test_progress_bar():
    assert progress_bar(10, 0) == "🔴 LIVE"
    assert len(progress_bar(0, 200)) == len(progress_bar(100, 200)) == 22
    assert progress_bar(0, 200).index(KNOB) == 0
    assert progress_bar(199, 200).index(KNOB) == 21


def test_parse_artist_title():
    f = MusicCog._parse_artist_title
    assert f("Rick Astley - Never Gonna Give You Up (Official Video)") == (
        "Rick Astley",
        "Never Gonna Give You Up",
    )
    assert f("Queen – Bohemian Rhapsody [Lyrics]") == ("Queen", "Bohemian Rhapsody")
    assert f("no separator here")[0] is None


class _FakePlayer:
    def __init__(self, n):
        self.queue = [{"title": f"T{i + 1}", "duration": 200} for i in range(n)]
        self.current = {"title": "cur", "duration": 100}


def test_build_queue_embed_pagination():
    p = _FakePlayer(25)
    _, total, page = build_queue_embed(p, 0)
    assert total == 3 and page == 0
    _, _, clamped = build_queue_embed(p, 99)
    assert clamped == 2  # кламп
    e2, _, _ = build_queue_embed(p, 2)
    assert "T21" in e2.description and "T25" in e2.description
    assert "T20" not in e2.description
