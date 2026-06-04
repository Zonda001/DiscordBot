"""Власна довідка: hybrid-команда, що працює і як !help, і як /help.

Замінює стандартний DefaultHelpCommand гарним ембедом із групуванням по cogs.
"""
import discord
from discord.ext import commands


class HelpCog(commands.Cog, name="Довідка"):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", aliases=["h", "commands"])
    async def help_cmd(self, ctx, *, command: str = None):
        """Список усіх команд або довідка по конкретній: help play"""
        prefix = "/" if ctx.interaction else ctx.prefix

        if command:
            cmd = self.bot.get_command(command.lstrip("/!").strip())
            if cmd is None:
                return await ctx.send(f"❌ Команда `{command}` не знайдена.")
            embed = discord.Embed(
                title=f"ℹ️ {prefix}{cmd.qualified_name}",
                description=cmd.help or cmd.description or "Без опису.",
                color=discord.Color.blurple(),
            )
            usage = f"{prefix}{cmd.qualified_name} {cmd.signature}".strip()
            embed.add_field(name="Використання", value=f"`{usage}`", inline=False)
            if cmd.aliases:
                embed.add_field(
                    name="Аліаси",
                    value=", ".join(f"`{a}`" for a in cmd.aliases),
                    inline=False,
                )
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="🤖 Команди бота",
            description=f"Префікс: `{prefix}` • деталі: `{prefix}help <команда>`",
            color=discord.Color.blurple(),
        )
        for cog_name, cog in self.bot.cogs.items():
            cmds = [c for c in cog.get_commands() if not c.hidden]
            if not cmds:
                continue
            names = " ".join(f"`{c.name}`" for c in sorted(cmds, key=lambda c: c.name))
            embed.add_field(name=cog_name, value=names, inline=False)
        embed.set_footer(text=f"Усього команд: {len(self.bot.commands)}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
