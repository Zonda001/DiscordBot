"""Утиліти музичного cog: формати, ембеди, yt-dlp, DJ-логіка, аудіофільтри."""
import logging
import math
import re

import discord
import yt_dlp

from discord_bot import config

def member_is_dj(member, dj_role_id) -> bool:
    """Чи може учасник вільно керувати музикою.

    True, якщо DJ-роль не задана (керують усі), або в учасника є право
    administrator, або він має саме цю роль. Чиста функція — тестовна.
    """
    if not dj_role_id:
        return True
    perms = getattr(member, "guild_permissions", None)
    if perms is not None and getattr(perms, "administrator", False):
        return True
    return any(getattr(r, "id", None) == dj_role_id for r in getattr(member, "roles", []))


def votes_needed(listeners: int) -> int:
    """Скільки голосів треба для скіпу: більшість слухачів (не менше 1)."""
    return max(1, math.ceil(listeners / 2))


def _youtube_id(url: str):
    """Витягує 11-символьний YouTube video id з URL (або None)."""
    if not url:
        return None
    m = re.search(r"(?:v=|youtu\.be/|/watch\?v=|/embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None

log = logging.getLogger("bot.music")

# Час бездіяльності (сам у каналі), після якого бот від'єднується, сек.
IDLE_DISCONNECT_SECONDS = 120

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

_RECONNECT = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    '-user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"'
)

# Пресети аудіофільтрів ffmpeg (-af). Значення без пробілів — інакше зламає shlex.
# None = без фільтра. "normalize" вирівнює гучність між треками.
AUDIO_FILTERS = {
    "off": None,
    "normalize": "dynaudnorm=f=200:g=15",
    "bassboost": "bass=g=12,dynaudnorm=f=200",
    "treble": "treble=g=8",
    "nightcore": "asetrate=48000*1.25,aresample=48000,bass=g=2",
    "vaporwave": "asetrate=48000*0.82,aresample=48000,bass=g=4",
    "8d": "apulsator=hz=0.09",
    "earrape": "acrusher=level_in=4:level_out=8:bits=8:mode=log:aa=1",
}


def make_ffmpeg_options(filter_str: str | None = None, seek: int | None = None) -> dict:
    """Будує опції ffmpeg для FFmpegPCMAudio з опційним фільтром і перемоткою."""
    before = _RECONNECT
    if seek and seek > 0:
        before = f"-ss {seek} " + before  # швидка перемотка на вході (до -i)
    options = "-vn"
    if filter_str:
        options += f" -af {filter_str}"
    return {"before_options": before, "options": options}


def fmt_time(seconds: int) -> str:
    """Секунди -> mm:ss або h:mm:ss."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def progress_bar(position: int, duration: int, length: int = 22) -> str:
    """Текстовий прогрес-бар з повзунком."""
    if not duration or duration <= 0:
        return "🔴 LIVE"
    frac = min(1.0, max(0.0, position / duration))
    knob = min(length - 1, int(frac * length))
    return "─" * knob + "🔘" + "─" * (length - knob - 1)


QUEUE_PER_PAGE = 10


def build_queue_embed(player, page: int):
    """Будує ембед однієї сторінки черги. Повертає (embed, total_pages, page)."""
    q = player.queue
    total_pages = max(1, (len(q) + QUEUE_PER_PAGE - 1) // QUEUE_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * QUEUE_PER_PAGE
    chunk = q[start:start + QUEUE_PER_PAGE]

    embed = discord.Embed(title="📋 Черга треків", color=discord.Color.blue())
    if player.current:
        embed.add_field(
            name="▶️ Зараз грає",
            value=f"**{player.current['title']}**",
            inline=False,
        )
    lines = [f"`{start + i + 1:>2}.` **{t['title']}**" for i, t in enumerate(chunk)]
    embed.description = "\n".join(lines) if lines else "_черга порожня_"

    total_dur = sum(int(t.get("duration") or 0) for t in q)
    footer = f"Сторінка {page + 1}/{total_pages} • усього {len(q)} треків"
    if total_dur:
        footer += f" • ~{fmt_time(total_dur)}"
    embed.set_footer(text=footer)
    return embed, total_pages, page


def build_nowplaying_embed(player, voice):
    """Ембед 'зараз грає' з прогрес-баром. None, якщо нічого не грає."""
    if not player or not player.current:
        return None
    dur = int(player.current.get("duration") or 0)
    pos = min(player.position(), dur) if dur else player.position()
    paused = voice is not None and voice.is_paused()
    icon = "⏸️" if paused else "▶️"
    bar = progress_bar(pos, dur)
    time_line = (
        f"`{fmt_time(pos)}` {bar} `{fmt_time(dur)}`" if dur else f"`{fmt_time(pos)}` {bar}"
    )
    embed = discord.Embed(
        title="🎵 Зараз грає",
        description=f"**{player.current['title']}**\n\n{icon} {time_line}",
        color=discord.Color.orange() if paused else discord.Color.green(),
    )
    active = next((k for k, v in AUDIO_FILTERS.items() if v == player.audio_filter), None)
    meta = []
    if active and active != "off":
        meta.append(f"🎚️ {active}")
    if player.loop_song:
        meta.append("🔂 повтор треку")
    elif player.loop_queue:
        meta.append("🔁 повтор черги")
    meta.append(f"🔊 {int(player.volume * 100)}%")
    embed.add_field(name="​", value=" • ".join(meta), inline=False)
    if player.queue:
        embed.add_field(name="📋 Далі в черзі", value=f"{len(player.queue)} треків", inline=False)
    return embed


def get_cookie_opts():
    """Найкращі доступні налаштування cookies для yt-dlp."""
    import os

    if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
        return {"cookiefile": config.COOKIES_FILE}
    if config.COOKIES_FROM_BROWSER:
        return {"cookiesfrombrowser": (config.COOKIES_FROM_BROWSER,)}
    return {}


def _ytdl(extra=None):
    opts = {
        "format": "bestaudio[acodec=opus]/bestaudio[acodec=mp4a]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "cachedir": False,
        "no_cache_dir": True,
        "socket_timeout": 10,
        "retries": 3,
        "http_headers": BASE_HEADERS,
        **get_cookie_opts(),
    }
    if extra:
        opts.update(extra)
    return yt_dlp.YoutubeDL(opts)
