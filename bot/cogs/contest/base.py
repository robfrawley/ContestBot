import os
from datetime import datetime

import discord
from discord.ext import commands

from bot.cogs.contest.jobs import ContestJobs
from bot.cogs.contest.utils import get_submission_channel, get_logs_channel
from bot.config import Bot, settings
from bot.core.error_embed import create_logs_embed
from bot.utils.image_utils import resize_and_save_image
from bot.config import logger
from bot.cogs.contest.utils import build_discord_embed_with_role_ping, build_discord_embed_with_image_and_role_ping, build_discord_embed_with_thumbnail_and_role_ping


class ContestManager(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.server_config_collection = bot.db["ServerConfig"]
        self.jobs = ContestJobs(cog=self)

    async def track_image_upload(self, message: discord.Message):
        user_id = message.author.id
        guild_id = message.guild.id
        attachment = message.attachments[0] if message.attachments else None
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)
        submission_channel = await get_submission_channel(self.bot, message.guild.id)

        async def log_to_logs_channel(title, description, color=discord.Color.default(), image=None):
            if logs_channel:
                msg = await logs_channel.send(
                        embed=create_logs_embed(
                        title=title,
                        description=description,
                        color=color,
                        image=image,
                        thumbnails=message.author.avatar.url if message.author.avatar else None
                    )
                )
                return msg
            return None

        if not submission_channel:
            await log_to_logs_channel(
                title="Submission Channel Not Configured",
                description=f"{message.author.mention} attempted to submit but the submission channel is not set.\nUse `/contest_submission_channel` to set it.",
                color=discord.Color.red()
            )
            return

        if message.channel.id != submission_channel.id:
            return

        if not attachment:
            await log_to_logs_channel(
                title="No Attachment Found",
                description=f"{message.author.mention} submitted a message without an image attachment. Not taking any action.",
                color=discord.Color.orange()
            )
            return

        if not attachment.content_type or not attachment.content_type.startswith("image/"):
            logger.debug(f"Attachment content type is not an image: {attachment.content_type}")
            await message.reply(
                **build_discord_embed_with_role_ping(
                    title="Invalid Submission",
                    description=(
                        f"Invalid submission format of type `{attachment.content_type}` provided. **Please submit a single image file.**"
                    ),
                    roles=message.author.mention,
                    color=discord.Color.red()
                )
            )
            return

        if len(message.attachments) > 1:
            await message.reply(
                **build_discord_embed_with_image_and_role_ping(
                    title="Multiple Attachments Detected",
                    description=(
                        f"You included {len(message.attachments)} message attachments in your submission. "
                        f"**Only one image is allowed per submission.** "
                        f"Using the first image from your message for your submission; all others will be ignored. "
                        f"\n\n"
                        f"If you'd like to change your submission, send a new message with only the single image you'd like to submit for the contest."
                        f"\n\n"
                        f"The following image has been used for your submission:"
                    ),
                    image_url=attachment.url,
                    roles=message.author.mention,
                    color=discord.Color.red()
                )
            )

        current_month = datetime.now(settings.bot_timezone).strftime("%Y-%m")
        submissions = self.bot.db.submissions
        image_bytes = await attachment.read()

        folder_path = f"bot/data/submissions/{guild_id}"
        os.makedirs(folder_path, exist_ok=True)
        output_path = os.path.join(folder_path, f"{user_id}.webp")
        db_path = output_path.replace("\\", "/")

        try:
            await resize_and_save_image(image_bytes, output_path)
            logger.info(f"Resized and saved image for user {user_id} in guild {guild_id} to path {output_path} (mongodb path: {db_path}).")
        except Exception as e:
            await log_to_logs_channel(
                title="Image Processing Failed",
                description=f"{message.author.mention} submitted an image, but it couldn't be resized.\nError: `{str(e)}`",
                color=discord.Color.red()
            )
            return

        await submissions.delete_many({
            "user_id": user_id,
            "guild_id": guild_id,
            "month": current_month
        })

        await submissions.insert_one({
            "user_id": user_id,
            "guild_id": guild_id,
            "month": current_month,
            "file_path": db_path,
            "message_id": message.id
        })

        await log_to_logs_channel(
            title="New Contest Submission",
            description=f"{message.author.mention} submitted an image for the contest.",
            color=discord.Color.green(),
            image=attachment.url
        )

        await message.reply(
            **build_discord_embed_with_thumbnail_and_role_ping(
                title="Submission Received",
                description=(
                    f"Your submission has been received successfully! **Good luck in the contest!**"
                ),
                thumbnail_url=attachment.url,
                roles=message.author.mention,
                color=discord.Color.green()
            )
        )
