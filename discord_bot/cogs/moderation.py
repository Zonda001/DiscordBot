"""Модераційний cog (кікер з голосових каналів).

Базується на DS.py. Кікає користувачів зі списку цілей, щойно вони заходять
у будь-який голосовий канал сервера.

⚠️ Використовуй лише на власному сервері / за погодженням з адміністрацією.
Для роботи боту потрібне право "Move Members" і роль вища за ціль.

Покращення:
  * список цілей зберігається у data/targets.json (переживає перезапуск);
  * прибрано мертву перевірку токена;
  * команди вимагають прав адміністратора через стандартні checks.
"""
import json
import logging

import discord
from discord.ext import commands

from discord_bot import config

log = logging.getLogger("bot.moderation")

TARGETS_FILE = config.DATA_DIR / "targets.json"


class ModerationCog(commands.Cog, name="Модерація"):
    def __init__(self, bot):
        self.bot = bot
        self.targets: set[int] = self._load_targets()

    # ---- персистентність ----

    def _load_targets(self) -> set[int]:
        try:
            if TARGETS_FILE.exists():
                with open(TARGETS_FILE, "r", encoding="utf-8") as f:
                    return set(json.load(f))
        except Exception:
            log.exception("Не вдалося прочитати %s", TARGETS_FILE)
        return set()

    def _save_targets(self):
        try:
            with open(TARGETS_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted(self.targets), f)
        except Exception:
            log.exception("Не вдалося зберегти цілі")

    # ---- логіка кіку ----

    async def kick_from_voice(self, member: discord.Member, channel_name="невідомий канал") -> bool:
        guild = member.guild
        bot_member = guild.me
        perms = bot_member.guild_permissions
        if not (perms.move_members or perms.administrator):
            log.warning("Боту бракує прав для переміщення %s", member)
            return False
        if bot_member.top_role.position <= member.top_role.position:
            log.warning("Роль бота занизька для кіку %s", member)
            return False
        try:
            await member.move_to(None)
            log.info("Кікнув %s з '%s'", member, channel_name)
            return True
        except discord.Forbidden:
            log.warning("403 при кіку %s", member)
        except discord.HTTPException as e:
            log.warning("HTTP помилка при кіку %s: %s", member, e)
        return False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or member.id not in self.targets:
            return
        if after.channel is None:
            return
        if before.channel == after.channel:
            return  # просто мікрофон/камера — ігноруємо
        if member.voice and member.voice.channel:
            await self.kick_from_voice(member, member.voice.channel.name)

    # ---- команди (тільки адміни) ----

    @commands.hybrid_command(name="add_target")
    @commands.has_permissions(administrator=True)
    async def add_target(self, ctx, user_id: int):
        """Додати користувача до списку цілей кіку."""
        self.targets.add(user_id)
        self._save_targets()
        await ctx.send(f"✅ Додано ціль `{user_id}`. Усього: {len(self.targets)}")

    @commands.hybrid_command(name="remove_target")
    @commands.has_permissions(administrator=True)
    async def remove_target(self, ctx, user_id: int):
        """Видалити користувача зі списку цілей."""
        if user_id in self.targets:
            self.targets.discard(user_id)
            self._save_targets()
            await ctx.send(f"✅ Видалено ціль `{user_id}`.")
        else:
            await ctx.send("❌ Такого ID немає у списку.")

    @commands.hybrid_command(name="list_targets")
    @commands.has_permissions(administrator=True)
    async def list_targets(self, ctx):
        """Показати список цілей."""
        if not self.targets:
            return await ctx.send("📋 Список цілей порожній.")
        body = "\n".join(f"• {uid}" for uid in sorted(self.targets))
        await ctx.send(f"📋 **Цілі ({len(self.targets)}):**\n```{body}```")

    @commands.hybrid_command(name="kick_all")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(move_members=True)
    async def kick_all(self, ctx):
        """Кікнути всіх цілей, що зараз у голосових каналах."""
        kicked = 0
        for uid in list(self.targets):
            member = ctx.guild.get_member(uid)
            if member and member.voice and member.voice.channel:
                if await self.kick_from_voice(member, member.voice.channel.name):
                    kicked += 1
        await ctx.send(f"✅ Кікнуто {kicked} користувач(ів).")


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
