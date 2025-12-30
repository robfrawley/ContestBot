import os
import json
import discord # type: ignore
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
        alias_generator=lambda string: "".join(
            word.capitalize() if i else word for i, word in enumerate(string.split("_"))
        ),
        populate_by_name=True,
    )

    discordToken: str = Field(alias="DISCORD_TOKEN")
    mongoUri: str = Field(alias="MONGO_URI")
    mongo: Optional[AsyncIOMotorClient] = None

    scheduleShowSubmitChannel: Schedule = Field(alias="SCHEDULE_SHOW_SUBMIT_CHANNEL")
    scheduleHideSubmitChannel: Schedule = Field(alias="SCHEDULE_HIDE_SUBMIT_CHANNEL")
    scheduleMakeVotingForum: Schedule = Field(alias="SCHEDULE_SEND_VOTING_FORUM")
    scheduleShowVotingForum: Schedule = Field(alias="SCHEDULE_SHOW_VOTING_FORUM")
    scheduleHideVotingForum: Schedule = Field(alias="SCHEDULE_HIDE_VOTING_FORUM")
    scheduleAnncWinner: Schedule = Field(alias="SCHEDULE_ANNC_WINNER")
    scheduleEndsEvents: Schedule = Field(alias="SCHEDULE_ENDS_EVENTS")

    botTimezone: ZoneInfo = ZoneInfo("America/New_York")
    botAuthorName: str = Field(default="Contest Bot", alias="BOT_AUTHOR_NAME")
    botAuthorImgUrl: str | None = Field(default=None, alias="BOT_AUTHOR_IMG_URL")

    @field_validator("mongo", mode="after")
    @classmethod
    def build_mongo_client(cls, v, info):
        mongo_uri = info.data.get("mongoUri")
        if isinstance(mongo_uri, AsyncIOMotorClient):
            return mongo_uri
        return AsyncIOMotorClient(mongo_uri)

    @field_validator("botTimezone", mode="before")
    @classmethod
    def validate_timezone(cls, v):
        if isinstance(v, str):
            return ZoneInfo(v)
        return v

    @field_validator(
        "scheduleShowSubmitChannel",
        "scheduleHideSubmitChannel",
        "scheduleMakeVotingForum",
        "scheduleShowVotingForum",
        "scheduleHideVotingForum",
        "scheduleAnncWinner",
        "scheduleEndsEvents",
        mode="before"
    )
    @classmethod
    def parse_json_schedule(cls, v):
        if isinstance(v, str):
            return Schedule(**json.loads(v))
        return v


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

        if self.user is not None:
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
