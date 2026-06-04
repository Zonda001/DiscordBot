"""Музичний cog: відтворення з YouTube через yt-dlp.

Покращення відносно Music.py:
  * винесено в Cog, токен більше не в коді;
  * робоча довідка (через стандартний !help);
  * коректне очищення плеєрів при від'єднанні (немає витоку задач);
  * автовідключення, коли бот лишився сам у каналі;
  * нові команди: shuffle, remove, clear.
"""
import asyncio
import json
import logging
import random
import re
import time

import discord
import yt_dlp
from discord.ext import commands

from discord_bot import config
from discord_bot.playlists import PlaylistStore
from discord_bot.settings import settings
from discord_bot.spotify import is_spotify_url, spotify


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


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Невідома назва")
        self.url = data.get("url")
        self.duration = data.get("duration")

    @classmethod
    async def from_url(cls, url, *, loop, filter_str: str | None = None, seek: int | None = None):
        ytdl = _ytdl()

        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False)),
                timeout=20,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout — трек завантажується занадто довго.")

        if "entries" in data:
            data = data["entries"][0]

        # Шукаємо потік із найвищим бітрейтом серед аудіо (краща якість).
        audio_url = data.get("url")
        if not audio_url:
            best_abr = -1
            for fmt in data.get("formats", []):
                if fmt.get("acodec") not in (None, "none") and fmt.get("url"):
                    abr = fmt.get("abr") or 0
                    if abr > best_abr:
                        best_abr, audio_url = abr, fmt["url"]

        if not audio_url or not audio_url.startswith(("http://", "https://")):
            raise RuntimeError("Не вдалося отримати коректне посилання на аудіо.")

        ffmpeg_opts = make_ffmpeg_options(filter_str=filter_str, seek=seek)
        return cls(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts), data=data)


class MusicPlayer:
    """Плеєр на один сервер. Сам тягне наступний трек із черги."""

    def __init__(self, cog, guild: discord.Guild, text_channel: discord.abc.Messageable):
        self.cog = cog
        self.bot = cog.bot
        self.guild = guild
        self.text_channel = text_channel

        self.queue: list[dict] = []
        self.current: dict | None = None
        self.next_event = asyncio.Event()
        self.volume = 0.5
        self.loop_song = False
        self.loop_queue = False
        self.is_loading = False

        # активний -af фільтр (за замовчуванням з config.DEFAULT_FILTER)
        self.audio_filter: str | None = AUDIO_FILTERS.get(config.DEFAULT_FILTER)
        self._pending_seek: int | None = None   # одноразова перемотка
        self._restarting = False                # перезапуск поточного треку

        # Відстеження позиції відтворення (для прогрес-бару)
        self._start_ts: float | None = None     # monotonic-час старту потоку
        self._seek_offset: int = 0              # з якої секунди стартував потік
        self._paused_ts: float | None = None    # коли поставили на паузу
        self._paused_total: float = 0.0         # сумарно на паузі, сек
        self._recent: set[str] = set()           # id для автоплею (щоб не повторювати)

        self._task = self.bot.loop.create_task(self.player_loop())

    @property
    def voice(self) -> discord.VoiceClient | None:
        return self.guild.voice_client

    def play_next(self, error=None):
        if error:
            log.error("Player error: %s", error)
        self.bot.loop.call_soon_threadsafe(self.next_event.set)

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next_event.clear()

            if not self.loop_song:
                if not self.queue:
                    nxt = await self._maybe_autoplay()
                    if nxt:
                        self.queue.append(nxt)
                    else:
                        await self.next_event.wait()
                        continue
                self.current = self.queue.pop(0)
                # При перезапуску (зміна фільтра/seek) не дублюємо трек у loop_queue
                if self.loop_queue and not self._restarting:
                    self.queue.append(self.current)
            self._restarting = False

            voice = self.voice
            if voice is None:
                # бота відключили — завершуємо плеєр
                return

            seek = self._pending_seek
            self._pending_seek = None

            self.is_loading = True
            try:
                source = await YTDLSource.from_url(
                    self.current["url"],
                    loop=self.bot.loop,
                    filter_str=self.audio_filter,
                    seek=seek,
                )
                source.volume = self.volume
                voice.play(source, after=self.play_next)

                # старт відліку позиції
                self._seek_offset = seek or 0
                self._start_ts = time.monotonic()
                self._paused_ts = None
                self._paused_total = 0.0

                embed = discord.Embed(
                    title="🎵 Зараз грає",
                    description=f"**{source.title}**",
                    color=discord.Color.green(),
                )
                if self.queue:
                    embed.add_field(name="📋 У черзі", value=f"{len(self.queue)} треків")
                await self.text_channel.send(embed=embed)
            except Exception as e:
                log.warning("Помилка з треком '%s': %s", self.current.get("title", "?"), e)
                await self.text_channel.send(
                    f"⚠️ Пропускаю трек (**{self.current.get('title', 'невідомий')}**): {e}"
                )
                self.is_loading = False
                if self.loop_song:
                    await asyncio.sleep(3)
                continue
            finally:
                self.is_loading = False

            await self.next_event.wait()

    def position(self) -> int:
        """Поточна позиція відтворення в секундах (з урахуванням пауз/seek)."""
        if self._start_ts is None:
            return 0
        now = self._paused_ts if self._paused_ts is not None else time.monotonic()
        elapsed = now - self._start_ts - self._paused_total
        return self._seek_offset + max(0, int(elapsed))

    def mark_pause(self):
        if self._paused_ts is None:
            self._paused_ts = time.monotonic()

    def mark_resume(self):
        if self._paused_ts is not None:
            self._paused_total += time.monotonic() - self._paused_ts
            self._paused_ts = None

    def restart_current(self, seek: int | None = None) -> bool:
        """Перезапускає поточний трек (для зміни фільтра або перемотки)."""
        voice = self.voice
        if not self.current or voice is None:
            return False
        self._pending_seek = seek
        self._restarting = True
        self.queue.insert(0, self.current)
        voice.stop()  # after-callback розбудить player_loop, який підхопить трек
        return True

    async def _maybe_autoplay(self):
        """Якщо увімкнено автоплей — повертає схожий трек, інакше None."""
        if not self.current or not settings.get(self.guild.id, "autoplay"):
            return None
        return await self._fetch_related()

    async def _fetch_related(self):
        """Тягне трек із YouTube Mix (радіо) останнього треку."""
        vid = _youtube_id(self.current.get("url", ""))
        if not vid:
            return None
        mix_url = f"https://www.youtube.com/watch?v={vid}&list=RD{vid}"
        try:
            ytdl = _ytdl({"extract_flat": True, "playlistend": 20})
            data = await asyncio.wait_for(
                self.bot.loop.run_in_executor(
                    None, lambda: ytdl.extract_info(mix_url, download=False)
                ),
                timeout=15,
            )
        except Exception as e:
            log.warning("Автоплей: не вдалося отримати радіо: %s", e)
            return None
        if len(self._recent) > 300:
            self._recent.clear()
        self._recent.add(vid)
        for e in data.get("entries") or []:
            if not e:
                continue
            eid = e.get("id")
            if eid and eid not in self._recent:
                self._recent.add(eid)
                return {
                    "url": e.get("url") or f"https://youtube.com/watch?v={eid}",
                    "title": e.get("title", "Автоплей"),
                    "duration": e.get("duration", 0),
                }
        return None

    def destroy(self):
        """Зупиняє плеєр і чистить ресурси."""
        self.queue.clear()
        self.current = None
        if self._task and not self._task.done():
            self._task.cancel()


class QueueView(discord.ui.View):
    """Інтерактивна пагінація черги через кнопки."""

    def __init__(self, player: "MusicPlayer", page: int = 0, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.player = player
        self.page = page
        self.message: discord.Message | None = None
        self._sync_buttons()

    def _sync_buttons(self):
        _, total_pages, self.page = build_queue_embed(self.player, self.page)
        at_first = self.page <= 0
        at_last = self.page >= total_pages - 1
        self.first_btn.disabled = self.prev_btn.disabled = at_first
        self.last_btn.disabled = self.next_btn.disabled = at_last

    async def _render(self, interaction: discord.Interaction):
        embed, _, self.page = build_queue_embed(self.player, self.page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction, button):
        self.page = 0
        await self._render(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction, button):
        self.page -= 1
        await self._render(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction, button):
        self.page += 1
        await self._render(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction, button):
        _, total_pages, _ = build_queue_embed(self.player, self.page)
        self.page = total_pages - 1
        await self._render(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class NowPlayingView(discord.ui.View):
    """Кнопки керування під ембедом 'зараз грає'."""

    def __init__(self, cog, guild_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id
        self.message: discord.Message | None = None

    def _pv(self, interaction):
        player = self.cog.players.get(self.guild_id)
        voice = interaction.guild.voice_client if interaction.guild else None
        return player, voice

    async def _refresh(self, interaction):
        player, voice = self._pv(interaction)
        embed = build_nowplaying_embed(player, voice)
        if embed is None:
            for c in self.children:
                c.disabled = True
            await interaction.response.edit_message(
                content="⏹️ Відтворення завершено.", embed=None, view=self
            )
            self.stop()
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary)
    async def toggle_btn(self, interaction, button):
        player, voice = self._pv(interaction)
        if voice and voice.is_playing():
            voice.pause()
            if player:
                player.mark_pause()
        elif voice and voice.is_paused():
            voice.resume()
            if player:
                player.mark_resume()
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction, button):
        _, voice = self._pv(interaction)
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()
        await interaction.response.defer()
        await asyncio.sleep(1.5)  # дати player_loop підвантажити наступний трек
        player, voice = self._pv(interaction)
        embed = build_nowplaying_embed(player, voice)
        if self.message:
            try:
                await self.message.edit(
                    content=None if embed else "⏹️ Черга завершена.",
                    embed=embed,
                    view=self,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_btn(self, interaction, button):
        player, _ = self._pv(interaction)
        if player:
            if not player.loop_song and not player.loop_queue:
                player.loop_song = True
            elif player.loop_song:
                player.loop_song, player.loop_queue = False, True
            else:
                player.loop_queue = False
        await self._refresh(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle_btn(self, interaction, button):
        player, _ = self._pv(interaction)
        if player and len(player.queue) > 1:
            random.shuffle(player.queue)
        await self._refresh(interaction)

    @discord.ui.button(emoji="⭐", style=discord.ButtonStyle.success)
    async def fav_btn(self, interaction, button):
        player, _ = self._pv(interaction)
        if not player or not player.current:
            return await interaction.response.send_message(
                "❌ Зараз нічого не грає.", ephemeral=True
            )
        added = self.cog.favorites.add(interaction.user.id, player.current)
        msg = (
            f"⭐ Додано в обране: **{player.current['title']}**"
            if added
            else "ℹ️ Цей трек уже в твоєму обраному."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction, button):
        player, voice = self._pv(interaction)
        if player:
            player.queue.clear()
            player.loop_song = player.loop_queue = False
        if voice:
            voice.stop()
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(content="⏹️ Зупинено.", embed=None, view=self)
        self.stop()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class SearchSelectView(discord.ui.View):
    """Випадайка з топ-5 результатів пошуку (!search)."""

    def __init__(self, cog, ctx, entries, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.entries = entries
        self.message: discord.Message | None = None
        options = []
        for i, e in enumerate(entries):
            title = (e.get("title") or "Невідомо")[:95]
            dur = e.get("duration")
            options.append(
                discord.SelectOption(
                    label=f"{i + 1}. {title}"[:100],
                    description=fmt_time(int(dur)) if dur else None,
                    value=str(i),
                )
            )
        self.pick.options = options

    async def interaction_check(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Це меню не для тебе 🙂", ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="Обери трек...")
    async def pick(self, interaction, select):
        e = self.entries[int(select.values[0])]
        url = (
            e.get("url")
            or e.get("webpage_url")
            or (f"https://youtube.com/watch?v={e['id']}" if e.get("id") else None)
        )
        player = self.cog.get_player(self.ctx)
        player.queue.append(
            {"url": url, "title": e.get("title", "Невідомо"), "duration": e.get("duration", 0)}
        )
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(
            content=f"✅ Додано в чергу: **{e.get('title', 'Невідомо')}**", view=self
        )
        self.stop()
        vc = self.ctx.voice_client
        if vc and not vc.is_playing() and not player.is_loading:
            player.next_event.set()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class MusicCog(commands.Cog, name="Музика"):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}
        # guild_id -> task автовідключення
        self._idle_tasks: dict[int, asyncio.Task] = {}
        self.favorites = FavoritesStore(config.DATA_DIR / "favorites.json")
        self.playlists = PlaylistStore()

    # ---- допоміжне ----

    def get_player(self, ctx) -> MusicPlayer:
        player = self.players.get(ctx.guild.id)
        if player is None:
            player = MusicPlayer(self, ctx.guild, ctx.channel)
            self.players[ctx.guild.id] = player
        return player

    async def cleanup(self, guild: discord.Guild):
        player = self.players.pop(guild.id, None)
        if player:
            player.destroy()
        task = self._idle_tasks.pop(guild.id, None)
        if task:
            task.cancel()
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

    # ---- автовідключення, коли бот сам ----

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        voice = member.guild.voice_client
        if voice is None:
            return

        humans = [m for m in voice.channel.members if not m.bot]
        gid = member.guild.id

        if not humans:
            if gid not in self._idle_tasks:
                self._idle_tasks[gid] = self.bot.loop.create_task(
                    self._idle_disconnect(member.guild)
                )
        else:
            task = self._idle_tasks.pop(gid, None)
            if task:
                task.cancel()

    async def _idle_disconnect(self, guild: discord.Guild):
        try:
            await asyncio.sleep(IDLE_DISCONNECT_SECONDS)
            voice = guild.voice_client
            if voice and not [m for m in voice.channel.members if not m.bot]:
                player = self.players.get(guild.id)
                if player:
                    await player.text_channel.send("👋 Нікого немає поруч — від'єднуюсь.")
                await self.cleanup(guild)
        except asyncio.CancelledError:
            pass
        finally:
            self._idle_tasks.pop(guild.id, None)

    # ---- команди ----

    @commands.hybrid_command(name="join", aliases=["connect"])
    async def join(self, ctx):
        """Приєднати бота до твого голосового каналу."""
        if ctx.author.voice is None:
            return await ctx.send("❌ Ти не в голосовому каналі!")
        channel = ctx.author.voice.channel
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"✅ Приєднався до **{channel}**")

    @commands.hybrid_command(name="leave", aliases=["disconnect", "dc"])
    async def leave(self, ctx):
        """Вийти з голосового каналу та очистити чергу."""
        if ctx.voice_client:
            await self.cleanup(ctx.guild)
            await ctx.send("👋 Від'єднався.")
        else:
            await ctx.send("❌ Бот не в голосовому каналі.")

    @commands.hybrid_command(name="play", aliases=["p"])
    async def play(self, ctx, *, search: str):
        """Відтворити трек/плейлист з YouTube (URL або пошуковий запит)."""
        await ctx.defer()  # запас часу для slash (yt-dlp може думати >3с)
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send("❌ Приєднайся до голосового каналу або `!join`")

        player = self.get_player(ctx)

        # Spotify-посилання -> резолв назв і пошук відповідників на YouTube
        if is_spotify_url(search):
            return await self._play_spotify(ctx, player, search)

        searching_msg = await ctx.send(f"🔍 Шукаю: **{search}**...")

        if "music.youtube.com" in search:
            search = search.replace("music.youtube.com", "youtube.com")

        loop = asyncio.get_event_loop()
        try:
            is_playlist = (
                "playlist" in search.lower() or "list=" in search or "/sets/" in search
            )
            if is_playlist:
                ytdl = _ytdl({"extract_flat": True, "playlistend": 500})
                timeout = 20
            else:
                ytdl = _ytdl()
                timeout = 15
            query = search if search.startswith("http") else f"ytsearch:{search}"
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False)),
                timeout=timeout,
            )
        except Exception as e:
            log.warning("Помилка пошуку '%s': %s", search, e)
            return await searching_msg.edit(content="❌ Не вдалося обробити запит. Спробуй інший URL/назву.")

        if not data:
            return await searching_msg.edit(content="❌ Нічого не знайдено!")

        added = self._enqueue(player, data, search)
        if added == 0:
            return await searching_msg.edit(content="❌ Нічого не додано (порожній результат).")

        await searching_msg.delete()
        if added == 1:
            await ctx.send(f"✅ Додано в чергу: **{player.queue[-1]['title'] if player.queue else player.current['title']}**")
        else:
            await ctx.send(f"✅ Додано **{added}** треків у чергу.")

        if not ctx.voice_client.is_playing() and not player.is_loading:
            player.next_event.set()

    async def _play_spotify(self, ctx, player, url):
        if not spotify.enabled:
            return await ctx.send(
                "❌ Spotify не налаштовано. Додай `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` у .env."
            )
        msg = await ctx.send("🔍 Обробляю Spotify-посилання...")
        try:
            name, names = await spotify.resolve(url)
        except Exception as e:
            log.warning("Spotify resolve error: %s", e)
            return await msg.edit(content="❌ Не вдалося обробити Spotify-посилання.")
        if not names:
            return await msg.edit(content="❌ Spotify: треків не знайдено.")
        for n in names:
            player.queue.append({"url": f"ytsearch1:{n}", "title": n, "duration": 0})
        title = f" з «{name}»" if name else ""
        await msg.edit(content=f"✅ Spotify{title}: додано **{len(names)}** трек(ів).")
        if ctx.voice_client and not ctx.voice_client.is_playing() and not player.is_loading:
            player.next_event.set()

    @commands.hybrid_command(name="search", aliases=["find"])
    async def search(self, ctx, *, query: str):
        """Пошук на YouTube з вибором із топ-5 результатів."""
        await ctx.defer()
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send("❌ Приєднайся до голосового каналу або `!join`")

        loop = asyncio.get_event_loop()
        try:
            ytdl = _ytdl({"extract_flat": True})
            data = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: ytdl.extract_info(f"ytsearch5:{query}", download=False)
                ),
                timeout=15,
            )
        except Exception as e:
            log.warning("Помилка пошуку '%s': %s", query, e)
            return await ctx.send("❌ Помилка пошуку.")

        entries = [e for e in (data.get("entries") or []) if e][:5]
        if not entries:
            return await ctx.send("❌ Нічого не знайдено.")

        view = SearchSelectView(self, ctx, entries)
        view.message = await ctx.send(f"🔎 Результати для **{query}**:", view=view)

    @staticmethod
    def _enqueue(player: MusicPlayer, data: dict, search: str) -> int:
        """Додає трек(и) у чергу, повертає кількість доданих."""
        def track(entry):
            url = entry.get("webpage_url") or entry.get("url")
            if not url and entry.get("id"):
                url = f"https://youtube.com/watch?v={entry['id']}"
            return {
                "url": url,
                "title": entry.get("title", "Невідома назва"),
                "duration": entry.get("duration", 0),
            } if url else None

        added = 0
        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            single_search = "ytsearch" in search or (
                not any(x in search for x in ["playlist", "list="]) and len(entries) == 1
            )
            if single_search and entries:
                t = track(entries[0])
                if t:
                    player.queue.append(t)
                    added = 1
            else:
                for entry in entries[:500]:
                    t = track(entry)
                    if t:
                        player.queue.append(t)
                        added += 1
        else:
            t = track(data) or {
                "url": data.get("webpage_url", search),
                "title": data.get("title", "Невідома назва"),
                "duration": data.get("duration", 0),
            }
            player.queue.append(t)
            added = 1
        return added

    @commands.hybrid_command(name="pause")
    async def pause(self, ctx):
        """Пауза."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            player = self.players.get(ctx.guild.id)
            if player:
                player.mark_pause()
            await ctx.send("⏸️ Пауза")
        else:
            await ctx.send("❌ Нічого не відтворюється.")

    @commands.hybrid_command(name="resume")
    async def resume(self, ctx):
        """Продовжити після паузи."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            player = self.players.get(ctx.guild.id)
            if player:
                player.mark_resume()
            await ctx.send("▶️ Відтворення відновлено")
        else:
            await ctx.send("❌ Музика не на паузі.")

    @commands.hybrid_command(name="skip", aliases=["next", "s"])
    async def skip(self, ctx):
        """Пропустити поточний трек."""
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("⏭️ Пропущено")
        else:
            await ctx.send("❌ Нічого не відтворюється.")

    @commands.hybrid_command(name="stop")
    async def stop(self, ctx):
        """Зупинити і очистити чергу (бот лишається в каналі)."""
        player = self.players.get(ctx.guild.id)
        if player:
            player.queue.clear()
            player.loop_song = player.loop_queue = False
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send("⏹️ Зупинено, чергу очищено.")

    @commands.hybrid_command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        """Показати чергу (з кнопками-сторінками, якщо треків багато)."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.queue:
            return await ctx.send("📭 Черга порожня.")

        embed, total_pages, _ = build_queue_embed(player, 0)
        if total_pages <= 1:
            return await ctx.send(embed=embed)

        view = QueueView(player)
        embed, _, _ = build_queue_embed(player, view.page)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="nowplaying", aliases=["now", "np", "current"])
    async def now_playing(self, ctx):
        """Що зараз грає + прогрес-бар і кнопки керування."""
        player = self.players.get(ctx.guild.id)
        embed = build_nowplaying_embed(player, ctx.voice_client)
        if embed is None:
            return await ctx.send("❌ Нічого не відтворюється.")
        view = NowPlayingView(self, ctx.guild.id)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="lyrics", aliases=["ly"])
    async def lyrics(self, ctx, *, query: str = None):
        """Текст пісні (за назвою або поточного треку): Виконавець - Назва"""
        if query is None:
            player = self.players.get(ctx.guild.id)
            if not player or not player.current:
                return await ctx.send("❌ Вкажи назву або увімкни трек: `!lyrics Артист - Пісня`")
            query = player.current["title"]

        artist, title = self._parse_artist_title(query)
        if not artist or not title:
            return await ctx.send(
                "❌ Не зміг розпізнати виконавця й назву.\nФормат: `!lyrics Виконавець - Назва`"
            )

        await ctx.typing()
        text = await self._fetch_lyrics(artist, title)
        if not text:
            return await ctx.send(f"❌ Текст для **{artist} — {title}** не знайдено.")

        embed = discord.Embed(
            title=f"📜 {artist} — {title}",
            description=text[:4096],
            color=discord.Color.purple(),
        )
        if len(text) > 4096:
            embed.set_footer(text="(текст обрізано)")
        await ctx.send(embed=embed)

    @staticmethod
    def _parse_artist_title(query: str):
        """Чистить назву YouTube і ділить на (виконавець, назва)."""
        import re

        q = re.sub(r"[\(\[].*?[\)\]]", "", query)  # прибрати (Official Video), [Lyrics]
        for junk in ("official video", "official audio", "lyrics", "mv", "hd", "4k"):
            q = re.sub(junk, "", q, flags=re.IGNORECASE)
        q = q.strip(" -–—|")
        for sep in (" - ", " – ", " — ", "-"):
            if sep in q:
                a, _, t = q.partition(sep)
                return a.strip(), t.strip()
        return None, None

    @staticmethod
    async def _fetch_lyrics(artist: str, title: str):
        import urllib.parse
        import aiohttp

        url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return (data.get("lyrics") or "").strip() or None
        except Exception as e:
            log.warning("Lyrics fetch error: %s", e)
            return None

    # ---- обране (per-user) ----

    @commands.hybrid_command(name="fav", aliases=["favadd", "like"])
    async def fav(self, ctx):
        """Додати поточний трек у твоє обране."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.current:
            return await ctx.send("❌ Зараз нічого не грає.")
        if self.favorites.add(ctx.author.id, player.current):
            await ctx.send(f"⭐ Додано в обране: **{player.current['title']}**")
        else:
            await ctx.send("ℹ️ Цей трек уже в твоєму обраному.")

    @commands.hybrid_command(name="favs", aliases=["favlist", "favourites"])
    async def favs(self, ctx):
        """Показати твоє обране."""
        items = self.favorites.get(ctx.author.id)
        if not items:
            return await ctx.send("⭐ Твоє обране порожнє. Додай трек через `!fav`.")
        lines = [f"`{i + 1:>2}.` **{t['title']}**" for i, t in enumerate(items[:25])]
        embed = discord.Embed(
            title=f"⭐ Обране — {ctx.author.display_name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        if len(items) > 25:
            embed.set_footer(text=f"...та ще {len(items) - 25}. Усього: {len(items)}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="favplay", aliases=["playfav"])
    async def favplay(self, ctx, index: int = None):
        """Зіграти обране: !favplay (усе) або !favplay 3 (один трек)."""
        items = self.favorites.get(ctx.author.id)
        if not items:
            return await ctx.send("⭐ Твоє обране порожнє.")

        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send("❌ Приєднайся до голосового каналу або `!join`")

        if index is None:
            chosen = items
        elif 1 <= index <= len(items):
            chosen = [items[index - 1]]
        else:
            return await ctx.send(f"❌ Номер має бути від 1 до {len(items)}.")

        player = self.get_player(ctx)
        for t in chosen:
            player.queue.append({"url": t["url"], "title": t["title"], "duration": 0})

        await ctx.send(f"⭐ Додано в чергу з обраного: **{len(chosen)}** трек(ів).")
        if not ctx.voice_client.is_playing() and not player.is_loading:
            player.next_event.set()

    @commands.hybrid_command(name="unfav", aliases=["favremove"])
    async def unfav(self, ctx, index: int):
        """Видалити трек з обраного за номером (як у !favs)."""
        removed = self.favorites.remove(ctx.author.id, index)
        if removed:
            await ctx.send(f"🗑️ Видалено з обраного: **{removed['title']}**")
        else:
            await ctx.send("❌ Невірний номер.")

    # ---- іменовані плейлисти (per-user) ----

    @commands.hybrid_group(name="playlist", aliases=["pl"], invoke_without_command=True)
    async def playlist(self, ctx):
        """Іменовані плейлисти: save/load/list/show/delete."""
        await ctx.send(
            "📂 Підкоманди: `save <назва>`, `load <назва>`, `list`, `show <назва>`, `delete <назва>`"
        )

    @playlist.command(name="save")
    async def pl_save(self, ctx, *, name: str):
        """Зберегти поточну чергу як плейлист."""
        player = self.players.get(ctx.guild.id)
        tracks = []
        if player:
            if player.current:
                tracks.append(player.current)
            tracks.extend(player.queue)
        if not tracks:
            return await ctx.send("❌ Черга порожня — нема що зберігати.")
        n = self.playlists.save(ctx.author.id, name, tracks)
        await ctx.send(f"💾 Плейлист **{name}** збережено ({n} треків).")

    @playlist.command(name="load")
    async def pl_load(self, ctx, *, name: str):
        """Завантажити плейлист у чергу."""
        tracks = self.playlists.get(ctx.author.id, name)
        if not tracks:
            return await ctx.send(f"❌ Плейлист **{name}** не знайдено.")
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send("❌ Приєднайся до голосового каналу або `!join`")
        player = self.get_player(ctx)
        for t in tracks:
            player.queue.append({"url": t["url"], "title": t["title"], "duration": 0})
        await ctx.send(f"📂 Завантажено **{name}**: +{len(tracks)} треків.")
        if not ctx.voice_client.is_playing() and not player.is_loading:
            player.next_event.set()

    @playlist.command(name="list")
    async def pl_list(self, ctx):
        """Список твоїх плейлистів."""
        names = self.playlists.names(ctx.author.id)
        if not names:
            return await ctx.send("📭 У тебе немає збережених плейлистів.")
        lines = [f"• **{n}** — {c} треків" for n, c in names.items()]
        embed = discord.Embed(
            title=f"📂 Плейлисти — {ctx.author.display_name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @playlist.command(name="show")
    async def pl_show(self, ctx, *, name: str):
        """Показати треки плейлиста."""
        tracks = self.playlists.get(ctx.author.id, name)
        if not tracks:
            return await ctx.send(f"❌ Плейлист **{name}** не знайдено.")
        lines = [f"`{i + 1:>2}.` {t['title']}" for i, t in enumerate(tracks[:25])]
        embed = discord.Embed(
            title=f"📂 {name}", description="\n".join(lines), color=discord.Color.gold()
        )
        if len(tracks) > 25:
            embed.set_footer(text=f"...та ще {len(tracks) - 25}")
        await ctx.send(embed=embed)

    @playlist.command(name="delete", aliases=["del"])
    async def pl_delete(self, ctx, *, name: str):
        """Видалити плейлист."""
        if self.playlists.delete(ctx.author.id, name):
            await ctx.send(f"🗑️ Плейлист **{name}** видалено.")
        else:
            await ctx.send(f"❌ Плейлист **{name}** не знайдено.")

    @commands.hybrid_command(name="autoplay", aliases=["radio"])
    async def autoplay(self, ctx, mode: str = None):
        """Автоплей схожих треків коли черга порожня: on/off."""
        if mode is None:
            cur = settings.get(ctx.guild.id, "autoplay")
            return await ctx.send(f"📻 Автоплей: {'увімкнено ✅' if cur else 'вимкнено ❌'}")
        on = mode.lower() in ("on", "true", "1", "yes", "вкл", "увімк")
        settings.set(ctx.guild.id, "autoplay", on)
        await ctx.send(f"📻 Автоплей {'увімкнено ✅' if on else 'вимкнено ❌'}")

    @commands.hybrid_command(name="volume", aliases=["vol"])
    async def volume(self, ctx, volume: int = None):
        """Гучність 0-100 (без аргументу — показати поточну)."""
        player = self.players.get(ctx.guild.id)
        if not player:
            return await ctx.send("❌ Музика не відтворюється.")
        if volume is None:
            return await ctx.send(f"🔊 Поточна гучність: {int(player.volume * 100)}%")
        if not 0 <= volume <= 100:
            return await ctx.send("❌ Гучність має бути від 0 до 100.")
        player.volume = volume / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = player.volume
        await ctx.send(f"🔊 Гучність: {volume}%")

    @commands.hybrid_command(name="loop")
    async def loop_command(self, ctx, mode: str = None):
        """Повтор: song / queue / off."""
        player = self.players.get(ctx.guild.id)
        if not player:
            return await ctx.send("❌ Музика не відтворюється.")
        if mode == "song":
            player.loop_song, player.loop_queue = True, False
            await ctx.send("🔂 Повтор треку увімкнено")
        elif mode == "queue":
            player.loop_song, player.loop_queue = False, True
            await ctx.send("🔁 Повтор черги увімкнено")
        elif mode == "off":
            player.loop_song = player.loop_queue = False
            await ctx.send("❌ Повтор вимкнено")
        else:
            status = "🔂 Трек" if player.loop_song else "🔁 Черга" if player.loop_queue else "❌ Вимкнено"
            await ctx.send(f"🔄 Статус: {status}\nВикористання: `!loop song/queue/off`")

    @commands.hybrid_command(name="shuffle")
    async def shuffle(self, ctx):
        """Перемішати чергу."""
        player = self.players.get(ctx.guild.id)
        if not player or len(player.queue) < 2:
            return await ctx.send("❌ У черзі замало треків для перемішування.")
        random.shuffle(player.queue)
        await ctx.send(f"🔀 Перемішано ({len(player.queue)} треків).")

    @commands.hybrid_command(name="remove", aliases=["rm"])
    async def remove(self, ctx, index: int):
        """Видалити трек із черги за номером (як у !queue)."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.queue:
            return await ctx.send("📭 Черга порожня.")
        if not 1 <= index <= len(player.queue):
            return await ctx.send(f"❌ Номер має бути від 1 до {len(player.queue)}.")
        removed = player.queue.pop(index - 1)
        await ctx.send(f"🗑️ Видалено: **{removed['title']}**")

    @commands.hybrid_command(name="clear")
    async def clear(self, ctx):
        """Очистити чергу (поточний трек продовжує грати)."""
        player = self.players.get(ctx.guild.id)
        if not player or not player.queue:
            return await ctx.send("📭 Черга вже порожня.")
        n = len(player.queue)
        player.queue.clear()
        await ctx.send(f"🧹 Чергу очищено ({n} треків).")

    @commands.hybrid_command(name="filter", aliases=["fx", "effect"])
    async def filter_cmd(self, ctx, name: str = None):
        """Аудіофільтр: off, normalize, bassboost, treble, nightcore, vaporwave, 8d, earrape."""
        player = self.players.get(ctx.guild.id)
        if name is None:
            current = next((k for k, v in AUDIO_FILTERS.items() if v == (player.audio_filter if player else None)), "off")
            opts = ", ".join(AUDIO_FILTERS.keys())
            return await ctx.send(f"🎚️ Поточний фільтр: **{current}**\nДоступні: {opts}")

        name = name.lower()
        if name not in AUDIO_FILTERS:
            return await ctx.send(f"❌ Невідомий фільтр. Доступні: {', '.join(AUDIO_FILTERS.keys())}")
        if not player:
            return await ctx.send("❌ Музика не відтворюється.")

        player.audio_filter = AUDIO_FILTERS[name]
        if player.current and ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            player.restart_current()
            await ctx.send(f"🎚️ Фільтр **{name}** застосовано (перезапускаю трек).")
        else:
            await ctx.send(f"🎚️ Фільтр **{name}** застосується до наступного треку.")

    @commands.hybrid_command(name="seek")
    async def seek(self, ctx, position: str):
        """Перемотати поточний трек: !seek 90 або !seek 1:30"""
        player = self.players.get(ctx.guild.id)
        if not player or not player.current:
            return await ctx.send("❌ Нічого не відтворюється.")

        # парсимо "90" або "1:30" або "1:02:03"
        try:
            parts = [int(p) for p in position.split(":")]
            seconds = 0
            for p in parts:
                seconds = seconds * 60 + p
        except ValueError:
            return await ctx.send("❌ Формат: `!seek 90` або `!seek 1:30`")

        dur = player.current.get("duration") or 0
        if dur and seconds >= dur:
            return await ctx.send(f"❌ Трек коротший ({dur} с).")

        if player.restart_current(seek=seconds):
            m, s = divmod(seconds, 60)
            await ctx.send(f"⏩ Перемотка на {m:02d}:{s:02d}")
        else:
            await ctx.send("❌ Не вдалося перемотати.")


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
