from discord_bot.cogs.dashboard import DashboardCog
from discord_bot.main import CombinedBot, INITIAL_COGS


class _Req:
    def __init__(self, token=None):
        self.cookies = {"dash_session": token} if token else {}


class _FakeBot:
    user = "Bot#1"
    guilds = [object(), object()]

    def is_ready(self):
        return True

    def get_cog(self, name):
        return None

    def get_guild(self, gid):
        return None


def test_auth():
    cog = DashboardCog.__new__(DashboardCog)
    cog.sessions = set()
    assert cog._authed(_Req("tok")) is False
    cog.sessions.add("tok")
    assert cog._authed(_Req("tok")) is True
    assert cog._authed(_Req()) is False


def test_status_no_music():
    cog = DashboardCog.__new__(DashboardCog)
    cog.bot = _FakeBot()
    s = cog._status()
    assert s["online"] is True
    assert s["guild_count"] == 2
    assert s["players"] == []


async def test_dashboard_loads():
    bot = CombinedBot()
    for ext in INITIAL_COGS:
        await bot.load_extension(ext)
    assert bot.get_cog("Дашборд") is not None
    await bot.close()
