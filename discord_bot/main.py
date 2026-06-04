"""Точка входу об'єднаного бота.

Запуск з кореня проєкту:
    python -m discord_bot.main
або:
    python run_bot.py
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from discord_bot import config
from discord_bot.settings import settings

log = logging.getLogger("bot")

LOG_FILE = config.DATA_DIR / "bot.log"
LOCK_FILE = config.DATA_DIR / "bot.lock"

INITIAL_COGS = [
    "discord_bot.cogs.music",
    "discord_bot.cogs.moderation",
    "discord_bot.cogs.admin",
    "discord_bot.cogs.help",
    "discord_bot.cogs.status",
    "discord_bot.cogs.dashboard",
]


def _setup_logging():
    """Консоль + ротований файл (5 МБ × 3)."""
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    fileh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fileh.setFormatter(fmt)
    root.addHandler(fileh)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_lock():
    """Не дає запустити другий інстанс. Знімає лок при виході."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            pid = None
        if pid and pid != os.getpid() and _pid_alive(pid):
            raise SystemExit(
                f"❌ Бот уже запущений (PID {pid}). Якщо це помилка — видали {LOCK_FILE}"
            )
    LOCK_FILE.write_text(str(os.getpid()))
    import atexit

    atexit.register(lambda: LOCK_FILE.unlink(missing_ok=True))


def _get_prefix(bot, message):
    """Динамічний префікс на сервер (+ згадка бота)."""
    prefix = config.COMMAND_PREFIX
    if message.guild:
        prefix = settings.get(message.guild.id, "prefix") or config.COMMAND_PREFIX
    return commands.when_mentioned_or(prefix)(bot, message)


class CombinedBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(
            command_prefix=_get_prefix,
            intents=intents,
            help_command=None,  # власна довідка у cogs/help.py
        )

    async def setup_hook(self):
        for ext in INITIAL_COGS:
            try:
                await self.load_extension(ext)
                log.info("Завантажено cog: %s", ext)
            except Exception:
                log.exception("Не вдалося завантажити cog: %s", ext)

    async def on_ready(self):
        log.info("Увійшов як %s (ID: %s)", self.user, self.user.id)
        log.info("Підключено до %d сервер(ів)", len(self.guilds))
        await self.change_presence(
            activity=discord.Game(name=f"{config.COMMAND_PREFIX}help")
        )
        await self._sync_slash()

    async def _sync_slash(self):
        """Синхронізує slash-команди по кожній гільдії (миттєва поява)."""
        if getattr(self, "_synced", False):
            return
        self._synced = True
        total = 0
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                total += len(synced)
            except Exception:
                log.exception("Не вдалося синхронізувати slash для %s", guild)
        log.info("Синхронізовано %d slash-команд(и) у %d гільдіях", total, len(self.guilds))

    async def on_command_error(self, ctx, error):
        """Глобальна обробка помилок команд."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Бракує аргументів. Дивись `{ctx.prefix}help {ctx.command}`")
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ У тебе недостатньо прав для цієї команди.")
            return
        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ Боту бракує прав: {perms}")
            return
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ Перевірку доступу не пройдено.")
            return
        log.exception("Помилка в команді %s", ctx.command, exc_info=error)
        await ctx.send(f"❌ Сталася помилка: {error}")


def main():
    _setup_logging()

    problems = config.validate()
    if problems:
        for p in problems:
            log.error("Конфіг: %s", p)
        raise SystemExit("❌ Виправ .env і запусти знову.")

    _acquire_lock()

    bot = CombinedBot()
    try:
        bot.run(config.TOKEN, log_handler=None)
    except discord.LoginFailure:
        raise SystemExit("❌ Невірний токен бота. Перевір DISCORD_BOT_TOKEN у .env")
    except discord.PrivilegedIntentsRequired:
        raise SystemExit(
            "❌ Увімкни Privileged Intents (Server Members + Message Content) "
            "у Developer Portal → Bot."
        )


if __name__ == "__main__":
    main()
