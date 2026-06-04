"""Пише data/status.json для desktop-панелі (онлайн, сервери, аптайм, треки)."""
import json
import logging
import time

from discord.ext import commands, tasks

from discord_bot import config

log = logging.getLogger("bot.status")

STATUS_FILE = config.DATA_DIR / "status.json"


class StatusCog(commands.Cog, name="Статус"):
    def __init__(self, bot):
        self.bot = bot
        self._start = time.time()
        self.writer.start()

    def cog_unload(self):
        self.writer.cancel()
        self._write({"online": False, "ts": time.time()})

    @tasks.loop(seconds=5)
    async def writer(self):
        self._write(self.build_status())

    @writer.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()
        self._start = time.time()

    def build_status(self) -> dict:
        """Поточний знімок стану (чистий, тестований)."""
        music = self.bot.get_cog("Музика")
        players = []
        if music:
            for gid, p in music.players.items():
                guild = self.bot.get_guild(gid)
                players.append(
                    {
                        "guild": guild.name if guild else str(gid),
                        "current": p.current["title"] if p.current else None,
                        "queue": len(p.queue),
                    }
                )
        return {
            "online": True,
            "user": str(self.bot.user) if self.bot.user else None,
            "guilds": len(self.bot.guilds),
            "uptime": int(time.time() - self._start),
            "players": players,
            "ts": time.time(),
        }

    def _write(self, data: dict):
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            log.exception("Не вдалося записати статус")


async def setup(bot):
    await bot.add_cog(StatusCog(bot))
