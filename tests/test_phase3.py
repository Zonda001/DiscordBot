import time

from panel.app import BotPanel
from discord_bot.cogs.status import StatusCog


def test_panel_fmt():
    assert BotPanel._fmt(59) == "00:59"
    assert BotPanel._fmt(125) == "02:05"
    assert BotPanel._fmt(3661) == "1:01:01"


class _FakeBot:
    user = "Bot#1"
    guilds = [object(), object()]

    def get_cog(self, name):
        return None

    def get_guild(self, gid):
        return None


def test_status_build():
    cog = StatusCog.__new__(StatusCog)  # без __init__ (не запускати tasks.loop)
    cog.bot = _FakeBot()
    cog._start = time.time() - 5
    s = cog.build_status()
    assert s["online"] is True
    assert s["guilds"] == 2
    assert s["uptime"] >= 4
    assert s["players"] == []
    assert s["user"] == "Bot#1"
