import discord
from discord.ext import commands

from bot.cogs.contest.utils import get_logs_channel, get_voting_channel, build_discord_embed
from bot.core.error_embed import create_logs_embed
from bot.config import logger


ALLOWED_REACTIONS_UNICODE = {"🏆", ":trophy:"}
ALLOWED_REACTIONS_CUSTOM_IDS = {}


class ContestReactionsWatcher(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent
    ):
        voting_channel = await get_voting_channel(self.bot, guild_id=payload.guild_id)

        if not voting_channel:
            logger.debug(f"No voting channel configured for guild {payload.guild_id}; ignoring reaction...")
            return

        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return

        # Fetch the channel (this will be the THREAD)
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(payload.channel_id)

        # We only care about thread messages
        if not isinstance(channel, discord.Thread):
            return

        # Check parent forum
        forum = channel.parent
        if forum is None or forum.id != voting_channel.id:
            return

        # get starter message
        starter_message = channel.starter_message

        if starter_message is None:
            # Not cached → fetch it
            starter_message = await channel.fetch_message(channel.id)

        if payload.message_id != starter_message.id:
            return

        # Emoji whitelist check
        emoji = payload.emoji

        allowed = (
            (emoji.is_unicode_emoji() and emoji.name in ALLOWED_REACTIONS_UNICODE) or
            (emoji.id in ALLOWED_REACTIONS_CUSTOM_IDS)
        )

        # Fetch user
        user = payload.member or await self.bot.fetch_user(payload.user_id)

        # Fetch message
        message = await channel.fetch_message(payload.message_id)

        if allowed:
            logger.debug(f"Emoji reaction {emoji} by user {user.id} on message {message.id} in thread {channel.id} allowed ({allowed})...")
            return

        # Remove reaction
        logger.debug(f"Emoji reaction {emoji} by user {user.id} on message {message.id} in thread {channel.id} NOT allowed ({allowed})...")
        await message.remove_reaction(payload.emoji, user)
