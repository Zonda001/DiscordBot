"""Плеєр на один сервер: черга, цикл відтворення, позиція, автоплей."""
import asyncio
import logging
import time

import discord

from discord_bot import config
from discord_bot.settings import settings

from .helpers import AUDIO_FILTERS, _youtube_id, _ytdl
from .source import YTDLSource

log = logging.getLogger("bot.music")

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
        self.skip_votes: set[int] = set()        # id тих, хто проголосував за скіп

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
                self.skip_votes.clear()  # новий трек — голоси за скіп скидаються

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
        self.skip_votes.clear()
        self.current = None
        if self._task and not self._task.done():
            self._task.cancel()
