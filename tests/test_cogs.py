from discord_bot.main import CombinedBot, INITIAL_COGS


async def test_load_all_cogs():
    bot = CombinedBot()
    for ext in INITIAL_COGS:
        await bot.load_extension(ext)

    names = {c.name for c in bot.commands}
    for expected in [
        "play", "queue", "fav", "help", "lyrics", "nowplaying",
        "setnick", "kick_all", "favplay",
    ]:
        assert expected in names, f"missing prefix command {expected}"

    slash = {c.name for c in bot.tree.get_commands()}
    for expected in ["play", "help", "fav", "setnick"]:
        assert expected in slash, f"missing slash command {expected}"

    await bot.close()
