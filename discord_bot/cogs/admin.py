"""Адмін-cog: керування нікнеймами учасників.

Базується на NewBot.py, але:
  * консольне меню (input у потоці) замінено на нормальні Discord-команди;
  * прибрано зміну аватарок — Discord API НЕ дозволяє боту міняти аватар
    іншого учасника (Member.edit() не має параметра avatar), тому той код
    у NewBot.py ніколи не працював.

Потрібне право бота "Manage Nicknames" (і роль вища за ціль).
"""
import asyncio
import logging

import discord
from discord.ext import commands

log = logging.getLogger("bot.admin")

MAX_NICK_LEN = 32


class AdminCog(commands.Cog, name="Адмін"):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="setnick")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def setnick(self, ctx, member: discord.Member, *, nick: str):
        """Змінити нікнейм одного учасника: !setnick @user Новий Нік"""
        if len(nick) > MAX_NICK_LEN:
            return await ctx.send(f"❌ Нікнейм не довший за {MAX_NICK_LEN} символів.")
        old = member.display_name
        try:
            await member.edit(nick=nick, reason=f"setnick від {ctx.author}")
            await ctx.send(f"✅ {old} → **{nick}**")
        except discord.Forbidden:
            await ctx.send("❌ Не можу змінити — роль учасника вища або бракує прав.")

    @commands.hybrid_command(name="resetnick")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnick(self, ctx, member: discord.Member):
        """Скинути нікнейм учасника: !resetnick @user"""
        try:
            await member.edit(nick=None, reason=f"resetnick від {ctx.author}")
            await ctx.send(f"✅ Нікнейм {member} скинуто.")
        except discord.Forbidden:
            await ctx.send("❌ Не можу скинути — роль вища або бракує прав.")

    @commands.hybrid_command(name="nickvoice")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nickvoice(self, ctx, *, nick: str):
        """Дати один нік усім у ТВОЄМУ голосовому каналі: !nickvoice Текст"""
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            return await ctx.send("❌ Ти не в голосовому каналі.")
        if len(nick) > MAX_NICK_LEN:
            return await ctx.send(f"❌ Нікнейм не довший за {MAX_NICK_LEN} символів.")

        members = [m for m in ctx.author.voice.channel.members if not m.bot]
        await self._bulk_nick(ctx, members, nick)

    @commands.hybrid_command(name="resetnickvoice")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnickvoice(self, ctx):
        """Скинути ніки всім у твоєму голосовому каналі."""
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            return await ctx.send("❌ Ти не в голосовому каналі.")
        members = [m for m in ctx.author.voice.channel.members if not m.bot]
        await self._bulk_nick(ctx, members, None)

    async def _bulk_nick(self, ctx, members, nick):
        if not members:
            return await ctx.send("❌ У каналі немає учасників.")
        ok = fail = 0
        for member in members:
            try:
                await member.edit(nick=nick, reason=f"масова зміна від {ctx.author}")
                ok += 1
                await asyncio.sleep(0.3)  # щадимо rate limit
            except discord.HTTPException:
                fail += 1
        verb = "скинуто" if nick is None else "змінено"
        await ctx.send(f"✅ Готово! {verb}: {ok}, помилок: {fail}")

    @commands.hybrid_command(name="members")
    @commands.has_permissions(manage_nicknames=True)
    async def members(self, ctx):
        """Коротка статистика учасників сервера."""
        humans = [m for m in ctx.guild.members if not m.bot]
        online = [m for m in humans if m.status != discord.Status.offline]
        embed = discord.Embed(title=f"👥 {ctx.guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Учасників (без ботів)", value=str(len(humans)))
        embed.add_field(name="🟢 Онлайн", value=str(len(online)))
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
