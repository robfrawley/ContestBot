import io

import random
import aiohttp
import discord

from discord import Message

from typing import Iterable
from typing import TypedDict
from typing import List, Tuple
from dataclasses import dataclass, field

from bot.config import settings
from bot.config import logger


async def get_submission_channel(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_channel(config["submission_channel"]) if "submission_channel" in config else None


async def get_voting_channel(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_channel(config["voting_channel"]) if "voting_channel" in config else None


async def get_contest_role(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_role(config["contest_role"]) if "contest_role" in config else None


async def get_contest_announcement_channel(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_channel(config["contest_announcement_channel"]) if "contest_announcement_channel" in config else None


async def get_contest_ping_role(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_role(config["contest_ping_role"]) if "contest_ping_role" in config else None


async def get_contest_archive_channel(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_channel(config["contest_archive_channel"]) if "contest_archive_channel" in config else None


async def get_logs_channel(bot, guild_id):
    config = await bot.db["ServerConfig"].find_one({"_id": guild_id})
    if not config:
        return None
    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except discord.NotFound:
            logger.warn(f"Guild not found. {guild_id}")
            return None
    return guild.get_channel(config["contest_logs_channel"]) if "contest_logs_channel" in config else None


async def get_discord_file_from_url(url: str, filename: str = None) -> discord.File:
    """
    Downloads a file from a URL and returns a discord.File object.

    :param url: The direct URL to the file.
    :param filename: Optional custom filename. If not provided, tries to infer from URL.
    :return: discord.File object
    :raises: Exception if the file can't be downloaded
    """
    if filename is None:
        filename = url.split("/")[-1] or "file"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warn(f"Failed to fetch file {filename} from {url}: HTTP {resp.status}")
                raise Exception(f"Failed to fetch file {filename} from {url}: HTTP {resp.status}")
            data = io.BytesIO(await resp.read())
            return discord.File(data, filename=filename)

@dataclass
class Winner:
    bot: discord.Client
    thread: discord.Thread
    user: discord.User | discord.Member
    attachment: discord.Attachment
    votes: int
    rolls: List[Tuple[int, int]] = field(default_factory=list)

    def __post_init__(self):
        roll_with_rerolls(self)

    async def async_init(self, guild: discord.Guild, submissions_collection):
        winner_data = await submissions_collection.find_one({"thread_id": self.thread_id})
        if winner_data:
            self.user = guild.get_member(winner_data["user_id"])

    @property
    def current_roll(self) -> Tuple[int, int]:
        return self.rolls[-1]

    @property
    def roll_total(self) -> int:
        return sum(self.current_roll)

    @property
    def user_mention(self) -> str:
        return self.user.mention

    @property
    def user_display_name(self) -> str:
        return self.user.display_name

    @property
    def thread_id(self) -> int:
        return self.thread.id

    @property
    def thread_mention(self) -> str:
        return self.thread.mention


def roll_2d10() -> Tuple[int, int]:
    return random.randint(1, 10), random.randint(1, 10)

def should_reroll(roll: Tuple[int, int]) -> bool:
    return sum(roll) <= 5

def roll_with_rerolls(winner: Winner, force: bool = False, max_rerolls: int = 2):
    if force or not winner.rolls:
        winner.rolls.append(roll_2d10())

    rerolls = 0
    while should_reroll(winner.current_roll) and rerolls < max_rerolls:
        winner.rolls.append(roll_2d10())
        rerolls += 1


IMAGE_TYPES = (
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
)

async def find_first_image_post_for_forum_thread(thread) -> Message | None:
    # Starter message first (cheap and common)
    starter = thread.starter_message
    if starter:
        for a in starter.attachments:
            if a.content_type in IMAGE_TYPES:
                return starter

    # Fallback: scan from oldest → newest
    async for msg in thread.history(oldest_first=True):
        for a in msg.attachments:
            if a.content_type in IMAGE_TYPES:
                return msg

    return None


class EmbedWithRolePingDict(TypedDict):
    embed: discord.Embed
    content: str


RoleLike = discord.Role | str
RolesArg = RoleLike | Iterable[RoleLike] | None


def build_discord_embed_with_thumbnail_and_image_and_role_ping(
    title: str = "",
    description: str = "",
    thumbnail_url: str = "",
    image_url: str = "",
    roles: RolesArg = None,
    color: discord.Color = discord.Color.blue()
) -> EmbedWithRolePingDict:
    if roles is None:
        role_list: list[RoleLike] = []
    elif isinstance(roles, (discord.Role, str)):
        role_list: list[RoleLike] = [roles]
    elif isinstance(roles, Iterable):
        role_list: list[RoleLike] = list(roles)
    else:
        raise TypeError(f"Invalid roles argument: {roles!r}")

    mentions: list[str] = [
        r.mention if isinstance(r, discord.Role) else r
        for r in role_list
    ]

    return {
        "embed": build_discord_embed_with_thumbnail_and_image(title, description, thumbnail_url, image_url, color),
        "content": " ".join(mentions) if mentions else "",
    }


def build_discord_embed_with_thumbnail_and_role_ping(
    title: str = "",
    description: str = "",
    thumbnail_url: str = "",
    roles: RolesArg = None,
    color: discord.Color = discord.Color.blue()
) -> EmbedWithRolePingDict:
    if roles is None:
        role_list: list[RoleLike] = []
    elif isinstance(roles, (discord.Role, str)):
        role_list: list[RoleLike] = [roles]
    elif isinstance(roles, Iterable):
        role_list: list[RoleLike] = list(roles)
    else:
        raise TypeError(f"Invalid roles argument: {roles!r}")
    
    mentions: list[str] = [
        r.mention if isinstance(r, discord.Role) else r
        for r in role_list
    ]

    return {
        "embed": build_discord_embed_with_thumbnail(title, description, thumbnail_url, color),
        "content": " ".join(mentions) if mentions else "",
    }


def build_discord_embed_with_image_and_role_ping(
    title: str = "",
    description: str = "",
    image_url: str = "",
    roles: RolesArg = None,
    color: discord.Color = discord.Color.blue()
) -> EmbedWithRolePingDict:
    if roles is None:
        role_list: list[RoleLike] = []
    elif isinstance(roles, (discord.Role, str)):
        role_list: list[RoleLike] = [roles]
    elif isinstance(roles, Iterable):
        role_list: list[RoleLike] = list(roles)
    else:
        raise TypeError(f"Invalid roles argument: {roles!r}")

    mentions: list[str] = [
        r.mention if isinstance(r, discord.Role) else r
        for r in role_list
    ]

    return {
        "embed": build_discord_embed_with_image(title, description, image_url, color),
        "content": " ".join(mentions) if mentions else "",
    }


def build_discord_embed_with_role_ping(
    title: str = "",
    description: str = "",
    roles: RolesArg = None,
    color: discord.Color = discord.Color.blue()
) -> EmbedWithRolePingDict:
    if roles is None:
        role_list: list[RoleLike] = []
    elif isinstance(roles, (discord.Role, str)):
        role_list: list[RoleLike] = [roles]
    elif isinstance(roles, Iterable):
        role_list: list[RoleLike] = list(roles)
    else:
        raise TypeError(f"Invalid roles argument: {roles!r}")
    
    mentions: list[str] = [
        r.mention if isinstance(r, discord.Role) else r
        for r in role_list
    ]

    return {
        "embed": build_discord_embed(title, description, color),
        "content": " ".join(mentions) if mentions else "",
    }


def build_discord_embed(
    title: str = "",
    description: str = "",
    color: discord.Color = discord.Color.blue()
) -> discord.Embed:
    embed = discord.Embed(
        title = title,
        description = description,
        color = color,
        timestamp = discord.utils.utcnow()
    )

    embed.set_author(
        name=settings.bot_author_name,
        icon_url=settings.bot_author_img_url
    )

    return embed


def build_discord_embed_with_thumbnail_and_image(
    title: str = "",
    description: str = "",
    thumbnail_url: str = "",
    image_url: str = "",
    color: discord.Color = discord.Color.blue()
) -> discord.Embed:
    embed = build_discord_embed(title, description, color)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if image_url:
        embed.set_image(url=image_url)

    return embed


def build_discord_embed_with_thumbnail(
    title: str = "",
    description: str = "",
    thumbnail_url: str = "",
    color: discord.Color = discord.Color.blue()
) -> discord.Embed:
    embed = build_discord_embed(title, description, color)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    return embed


def build_discord_embed_with_image(
    title: str = "",
    description: str = "",
    image_url: str = "",
    color: discord.Color = discord.Color.blue()
) -> discord.Embed:
    embed = build_discord_embed(title, description, color)

    if image_url:
        embed.set_image(url=image_url)

    return embed
