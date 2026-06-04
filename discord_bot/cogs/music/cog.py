"""MusicCog: команди музики (play/skip/queue/...), DJ-роль, обране, плейлисти."""
import asyncio
import logging
import random

import discord
from discord.ext import commands

from discord_bot import config
from discord_bot.playlists import PlaylistStore
from discord_bot.settings import settings
from discord_bot.spotify import is_spotify_url, spotify

from .helpers import (
    AUDIO_FILTERS,
    IDLE_DISCONNECT_SECONDS,
    build_nowplaying_embed,
    build_queue_embed,
    member_is_dj,
    votes_needed,
    _ytdl,
)
from .player import MusicPlayer
from .stores import FavoritesStore
from .views import NowPlayingView, QueueView, SearchSelectView

log = logging.getLogger("bot.music")

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

    def _is_dj(self, ctx) -> bool:
        """Чи має автор право вільно керувати музикою (DJ-роль/адмін, або DJ не задано)."""
        return member_is_dj(ctx.author, settings.get(ctx.guild.id, "dj_role_id"))

    def _try_skip(self, guild, voice, member) -> tuple[bool, str]:
        """Спроба скіпу: (чи_скіпнути, повідомлення).

        DJ/адмін (або коли DJ-роль не задано) скіпають миттєво. Інакше — голосування:
        треба більшість слухачів у каналі. Голосувати може лише той, хто в каналі.
        """
        if member_is_dj(member, settings.get(guild.id, "dj_role_id")):
            return True, "⏭️ Пропущено"
        player = self.players.get(guild.id)
        if player is None:
            return False, "❌ Музика не відтворюється."
        channel = voice.channel
        if member not in channel.members:
            return False, "❌ Щоб голосувати за скіп, зайди в голосовий канал бота."
        listener_ids = {m.id for m in channel.members if not m.bot}
        player.skip_votes.add(member.id)
        votes = len(player.skip_votes & listener_ids)
        needed = votes_needed(len(listener_ids))
        if votes >= needed:
            player.skip_votes.clear()
            return True, "⏭️ Пропущено (голосування)"
        return False, f"🗳️ Голос за скіп: **{votes}/{needed}**"

    @commands.hybrid_command(name="skip", aliases=["next", "s"])
    async def skip(self, ctx):
        """Пропустити поточний трек (з DJ-роллю — голосуванням)."""
        voice = ctx.voice_client
        if not (voice and (voice.is_playing() or voice.is_paused())):
            return await ctx.send("❌ Нічого не відтворюється.")
        did_skip, msg = self._try_skip(ctx.guild, voice, ctx.author)
        if did_skip:
            voice.stop()
        await ctx.send(msg)

    @commands.hybrid_command(name="stop")
    async def stop(self, ctx):
        """Зупинити і очистити чергу (бот лишається в каналі)."""
        if not self._is_dj(ctx):
            return await ctx.send("🔒 Лише DJ або адміністратор може зупиняти відтворення.")
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
        if not self._is_dj(ctx):
            return await ctx.send("🔒 Лише DJ або адміністратор може видаляти треки з черги.")
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
        if not self._is_dj(ctx):
            return await ctx.send("🔒 Лише DJ або адміністратор може очищати чергу.")
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

    @commands.hybrid_command(name="dj", aliases=["setdj"])
    @commands.has_permissions(manage_guild=True)
    async def dj(self, ctx, role: discord.Role = None):
        """DJ-роль: лише вона (та адміни) керує музикою. Без аргументу — показати поточну."""
        cur_id = settings.get(ctx.guild.id, "dj_role_id")
        if role is None:
            if cur_id:
                r = ctx.guild.get_role(cur_id)
                name = r.mention if r else f"`{cur_id}` (роль видалено?)"
                return await ctx.send(
                    f"🎧 Поточна DJ-роль: {name}\nЗняти: `{ctx.prefix}djclear`"
                )
            return await ctx.send(
                f"🎧 DJ-роль не задано — музикою керують усі.\n"
                f"Задати: `{ctx.prefix}dj @роль`"
            )
        settings.set(ctx.guild.id, "dj_role_id", role.id)
        await ctx.send(
            f"🎧 DJ-роль встановлено: {role.mention}.\n"
            f"Тепер `skip` — голосуванням (більшість слухачів), а `stop`/`clear`/`remove` — "
            f"лише DJ або адмін."
        )

    @commands.hybrid_command(name="djclear", aliases=["djoff"])
    @commands.has_permissions(manage_guild=True)
    async def dj_clear(self, ctx):
        """Зняти DJ-роль (керування музикою знову доступне всім)."""
        settings.set(ctx.guild.id, "dj_role_id", None)
        await ctx.send("🎧 DJ-роль знято — музикою знову керують усі.")


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
