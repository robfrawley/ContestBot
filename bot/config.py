import os
import json
import sys
import datetime
import discord # type: ignore
from discord.app_commands import AppCommand
from typing import Optional
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore
from discord import Message
from discord.ext import commands # type: ignore
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict # type: ignore
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient # type: ignore
from bot import ENV_FILE_PATH

exts = [
    "bot.cogs.contest"
]

class Schedule(BaseModel):
    day: int
    hour: int
    minute: int
    second: int = 0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")

    discord_token: str = Field(alias="DISCORD_TOKEN")
    mongo_uri: str = Field(alias="MONGO_URI")
    mongo: Optional[AsyncIOMotorClient] = None

    bot_timezone: ZoneInfo = Field(default=ZoneInfo("UTC"), alias="BOT_TIMEZONE")
    bot_author_name: str = Field(default="Contest Bot", alias="BOT_AUTHOR_NAME")
    bot_author_img_url: Optional[str] = Field(default=None, alias="BOT_AUTHOR_IMG_URL")

    schedule_show_submit_channel: Schedule = Field(alias="SCHEDULE_SHOW_SUBMIT_CHANNEL")
    schedule_hide_submit_channel: Schedule = Field(alias="SCHEDULE_HIDE_SUBMIT_CHANNEL")
    schedule_make_voting_forum: Schedule = Field(alias="SCHEDULE_SEND_VOTING_FORUM")
    schedule_show_voting_forum: Schedule = Field(alias="SCHEDULE_SHOW_VOTING_FORUM")
    schedule_hide_voting_forum: Schedule = Field(alias="SCHEDULE_HIDE_VOTING_FORUM")
    schedule_annc_winner: Schedule = Field(alias="SCHEDULE_ANNC_WINNER")
    schedule_ends_events: Schedule = Field(alias="SCHEDULE_ENDS_EVENTS")

    image_max_dimension: int = Field(default=3840, alias="IMAGE_MAX_DIMENSION")

    @field_validator("mongo", mode="after")
    @classmethod
    def build_mongo_client(cls, v, info):
        mongo_uri = info.data.get("mongo_uri")
        if isinstance(mongo_uri, AsyncIOMotorClient):
            return mongo_uri
        return AsyncIOMotorClient(mongo_uri)

    @field_validator("bot_timezone", mode="before")
    @classmethod
    def validate_timezone(cls, v):
        if isinstance(v, str):
            return ZoneInfo(v)
        return v

    @field_validator(
        "schedule_show_submit_channel",
        "schedule_hide_submit_channel",
        "schedule_make_voting_forum",
        "schedule_show_voting_forum",
        "schedule_hide_voting_forum",
        "schedule_annc_winner",
        "schedule_ends_events",
        mode="before"
    )
    @classmethod
    def parse_json_schedule(cls, v):
        if isinstance(v, str):
            return Schedule(**json.loads(v))
        return v


class ConsoleLogger:
    def __init__(self, debug_enabled: bool = True, timezone: ZoneInfo = ZoneInfo("UTC")):
        self.debug_enabled = debug_enabled
        self.timezone = timezone


    def _log(self, level: str, message: str, level_color: str = ""):
        timestamp = datetime.datetime.now(tz=self.timezone).strftime("%Y-%m-%d %H:%M:%S")
        dim_white = "\033[37;2m"
        reset_code = "\033[0m"
        padded_level = f"{level.ljust(8)}"
        colored_level = f"{level_color}{padded_level}{reset_code}"
        print(f"{dim_white}{timestamp}{reset_code} {colored_level} {message}", file=sys.stdout)


    def info(self, message: str):
        self._log("INFO", message, level_color="\033[34;1m")


    def debug(self, message: str):
        if self.debug_enabled:
            self._log("DEBUG", message, level_color="\033[93m")


    def warn(self, message: str):
        self._log("WARN", message, level_color="\033[91m")

    def warning(self, message: str):
        self.warn('UPDATE CODE CALL FROM WARNING TO WARN!')
        self.warn(message)


    def log_settings(self, settings: BaseSettings):
        self.info("Loaded configuration...")

        fields = settings.model_fields.keys()
        values = {field: getattr(settings, field) for field in fields}
        maxlen = max(len(name) for name in fields)

        for name, value in values.items():
            padded_name = f"\"{name}\"".ljust(maxlen + 2)
            self.debug(f"- {padded_name} = \"{value}\"")
    
    def log_commands(self, synced: AppCommand):
        logger.info(f"Synced \"{len(synced)}\" commands...")

        entries = []

        for command in synced:
            scope = "global" if command.guild_id is None else f"guild={command.guild_id}"
            entries.append((f"- \"{command.name}\"", scope))

        max_len = max(len(cmd) for cmd, _ in entries)

        for cmd, scope in entries:
            logger.debug(f"{cmd.ljust(max_len)} ({scope})")


settings = Settings()
logger = ConsoleLogger(debug_enabled=settings.debug_mode, timezone=settings.bot_timezone)
logger.log_settings(settings)


class Bot(commands.Bot):
    def __init__(self, command_prefix: str, intents: discord.Intents,  **kwargs):
        super().__init__(command_prefix, intents=intents, **kwargs)
        self.db = settings.mongo["contest_bot"]
        self.scheduler = AsyncIOScheduler()


    async def on_ready(self):
        logger.info("Loading extensions...")

        for ext in exts:
            try:
                await self.load_extension(ext)
                logger.debug(f"- \"{ext}\" (success)")
            except Exception as e:
                logger.warn(f"- \"{ext}\" (failure: {e})")

        logger.info("Syncing commands...")
        synced = await self.tree.sync()
        logger.log_commands(synced)

        if self.user is not None:
            logger.info(f"User \"{self.user.name}\" with id \"{self.user.id}\" is ready...")
        else:
            logger.warn("Bot user is None on ready event!")

        if not self.scheduler.running:
            logger.info("Starting scheduler...")
            self.scheduler.start()


    async def on_message(self, message: Message):
        if message.author.bot:
            return

        cogs = [
            ("ContestManager", "track_image_upload")
        ]

        for cog_name, func_name in cogs:
            cog = self.get_cog(cog_name)
            if cog:
                func = getattr(cog, func_name, None)
                if func:
                    await func(message)
                else:
                    logger.warn(f"Cog {cog_name} has no function {func_name}")
            else:
                logger.warn(f"Cog {cog_name} not found")

        await self.process_commands(message)
