import os
import discord # type: ignore
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore
from discord import Message
from discord.ext import commands # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict, BaseModel # type: ignore
from pydantic_settings.sources import camel_case_aliases # type: ignore
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
        env_aliases=camel_case_aliases(),
        extra="ignore",
    )

    discordToken: str
    mongoUri: str
    mongo: AsyncIOMotorClient
    scheduleShowSubmitChannel: Schedule
    scheduleHideSubmitChannel: Schedule
    scheduleMakeVotingForum: Schedule
    scheduleShowVotingForum: Schedule
    scheduleHideVotingForum: Schedule
    scheduleAnncWinner: Schedule
    scheduleEndsEvents: Schedule
    botTimezone: ZoneInfo = ZoneInfo("America/New_York")
    botAuthorName: str = "Contest Bot"
    botAuthorImgUrl: str = None

    @field_validator("mongo", mode="after")
    @classmethod
    def build_mongo_client(cls, v, values):
        return values["mongoUri"] if isinstance(values["mongoUri"], AsyncIOMotorClient) else AsyncIOMotorClient(values["mongoUri"])

    @field_validator("timezone", mode="before")
    @classmethod
    def validate_timezone(cls, v):
        return ZoneInfo(v) if isinstance(v, str) else throw ValueError(f"Invalid timezone value: {v}")


settings = Settings()

print("Configuration loaded successfully.")
print(f"Discord Token: {settings.discordToken}")
print(f"MongoDB URI: {settings.mongoUri}")
print(f"MongoDB Client: {settings.mongo}")
print(f"Schedule Open Submit Channel: {settings.scheduleShowSubmitChannel}")
print(f"Schedule Hide Submit Channel: {settings.scheduleHideSubmitChannel}")
print(f"Schedule Make Voting Forum: {settings.scheduleMakeVotingForum}")
print(f"Schedule Open Voting Forum: {settings.scheduleShowVotingForum}")
print(f"Schedule Hide Voting Forum: {settings.scheduleHideVotingForum}")
print(f"Schedule Announce Winner: {settings.scheduleAnncWinner}")
print(f"Schedule Ends Events: {settings.scheduleEndsEvents}")


class Bot(commands.Bot):
    def __init__(self, command_prefix: str, intents: discord.Intents,  **kwargs):
        super().__init__(command_prefix, intents=intents, **kwargs)
        self.db = settings.mongo["contest_bot"]
        self.scheduler = AsyncIOScheduler()


    async def on_ready(self):
        for ext in exts:
            try:
                await self.load_extension(ext)
            except Exception as e:
                print(f"Failed to load extension {ext}: {e}")

        print(f"Loaded All Cog")

        synced = await self.tree.sync()

        print(f"Synced {len(synced)} commands")
        print(f"{self.user.name} is ready")

        if not self.scheduler.running:
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
                    print(f"Cog {cog_name} has no function {func_name}")
            else:
                print(f"Cog {cog_name} not found")

        await self.process_commands(message)
