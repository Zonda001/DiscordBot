"""Інтерактивні View: пагінація черги, кнопки 'зараз грає', вибір пошуку."""
import asyncio
import logging
import random

import discord

from .helpers import build_nowplaying_embed, build_queue_embed, fmt_time

log = logging.getLogger("bot.music")

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
        if not (voice and (voice.is_playing() or voice.is_paused())):
            return await interaction.response.send_message(
                "❌ Нічого не відтворюється.", ephemeral=True
            )
        did_skip, msg = self.cog._try_skip(interaction.guild, voice, interaction.user)
        if not did_skip:
            return await interaction.response.send_message(msg, ephemeral=True)
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
