import discord #type: ignore
from bot.config import settings
from bot.config import Bot


if __name__ == "__main__":
    bot = Bot(command_prefix="c!", intents=discord.Intents.all(), help_command=None)
    bot.run(settings.discordToken)