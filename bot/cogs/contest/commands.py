import discord
from discord.ext import commands

from bot.cogs.contest.utils import get_logs_channel, get_contest_role, get_contest_announcement_channel, get_contest_ping_role, get_contest_archive_channel, get_submission_channel, get_voting_channel
from bot.core.error_embed import create_logs_embed


class ContestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.collection = self.bot.db["ServerConfig"]


    @commands.hybrid_command(name="contest_apply_role_to_all", description="Apply contest role to all members")
    async def contest_apply_role_to_all(self, ctx: commands.Context, *, role: discord.Role = None):
        await ctx.defer()

        logs_channel = await get_logs_channel(self.bot, guild_id=ctx.guild.id)
        role_name = role if role else await get_contest_role(self.bot, guild_id=ctx.guild.id)
        if logs_channel:
            if role_name:
                logs_embed = create_logs_embed(
                    title="Applying contest role",
                    description=f"Applying role of \"{role_name if role_name else 'None'}\" to {len(ctx.guild.members)} members",
                    color=discord.Color.green() if role_name else discord.Color.red()
                )
                await logs_channel.send(
                    embed=logs_embed
                )

        if role_name is None and logs_channel:
            print(f"Contest role not set for guild {ctx.guild.id}")
            await logs_channel.send("Please specify a role.")
            return
        else:
            for member in ctx.guild.members:
                if not member.bot:
                    try:
                        print(f"Adding {role_name} role to {member.name}")
                        #await member.add_roles(role_name, reason=f"Applying contest role to all member: {member.name}")
                    except Exception as e:
                        print(f"Failed to add role {role_name} to {member.name}: {e}")

        await ctx.send("Finished applying contest role to all members.")


    @commands.hybrid_command(name="contest_set_submission_channel", description="Select submission channel")
    async def contest_set_submission_channel(self, ctx: commands.Context, *, channel: discord.TextChannel = None):
        await ctx.defer()

        logs_channel = await get_logs_channel(self.bot, guild_id=ctx.guild.id)
        if logs_channel:
            logs_embed = create_logs_embed(
                title="Submission channel set",
                description=f"Submission channel set to <#{channel.id}>" if channel else "Submission channel unset",
                color=discord.Color.green() if channel else discord.Color.red()
            )
            await logs_channel.send(
                embed=logs_embed
            )

        if channel is None:
            channel = ctx.channel

        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"submission_channel": channel.id}},
                upsert=True)
            await ctx.send(f"<#{channel.id}> is set as submission channel")
        except Exception as e:
            if logs_channel:
                await logs_channel.send(
                    embed=create_logs_embed(
                        title="Error setting submission channel",
                        description=f"Error: {e}",
                        color=discord.Color.red()
                    )
                )
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_submission_channel", description="Get submission channel")
    async def contest_get_submission_channel(self, ctx: commands.Context):
        await ctx.defer()

        submission_channel = await get_submission_channel(self.bot, guild_id=ctx.guild.id)
        if submission_channel:
            await ctx.send(f"Submission channel is set to <#{submission_channel.id}>")
        else:
            await ctx.send("Submission channel is not set.")


    @commands.hybrid_command(name="contest_set_voting_channel", description="Select voting channel")
    async def contest_set_voting_channel(self, ctx: commands.Context, *, channel: discord.ForumChannel = None):
        await ctx.defer()
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.ForumChannel):
            await ctx.send("Please select a valid forum channel for voting.")
            return

        try:
            update = await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"voting_channel": channel.id}},
                upsert=True
            )
            if update.modified_count == 0:
                await ctx.send(f"Voting channel already set to <#{channel.id}>")
            else:
                await ctx.send(f"<#{channel.id}> is set as voting channel")
        except Exception as e:
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_voting_channel", description="Get voting channel")
    async def contest_get_voting_channel(self, ctx: commands.Context):
        await ctx.defer()

        voting_channel = await get_voting_channel(self.bot, guild_id=ctx.guild.id)
        if voting_channel:
            await ctx.send(f"Voting channel is set to <#{voting_channel.id}>")
        else:
            await ctx.send("Voting channel is not set.")


    @commands.hybrid_command(name="contest_set_role", description="Select contest role")
    async def contest_set_role(self, ctx: commands.Context, *, role: discord.Role = None):
        await ctx.defer()
        if role is None:
            await ctx.send("Please specify a role.")
            return
        if not isinstance(role, discord.Role):
            await ctx.send("Please select a valid role.")
            return

        bot_member = ctx.guild.me

        server_config = await self.collection.find_one({"_id": ctx.guild.id})
        announcement_channel = ctx.guild.get_channel(server_config.get("contest_announcement_channel"))
        if announcement_channel:
            if role not in announcement_channel.overwrites:
                overwrites = {
                    bot_member: discord.PermissionOverwrite(view_channel=True, manage_channels=True, send_messages=True,
                                                            manage_threads=True, read_message_history=True),
                    role: discord.PermissionOverwrite(view_channel=True, read_message_history=True,
                                                      send_messages=False),
                    ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False, read_message_history=False,
                                                                        send_messages=False)
                }
                await announcement_channel.edit(overwrites=overwrites)
            else:
                print("role already in announcement channel")

        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"contest_role": role.id}},
                upsert=True)
            await ctx.send(f"{role.mention} is set as contest role")
        except Exception as e:
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_role", description="Get contest role")
    async def contest_get_role(self, ctx: commands.Context):
        await ctx.defer()

        contest_role = await get_contest_role(self.bot, guild_id=ctx.guild.id)
        if contest_role:
            await ctx.send(f"Contest role is set to <@&{contest_role.id}>")
        else:
            await ctx.send("Contest role is not set.")


    @commands.hybrid_command(name="contest_set_announcement_channel", description="Select announcement channel")
    async def contest_set_announcement_channel(self, ctx: commands.Context, *, channel: discord.TextChannel = None):
        await ctx.defer()
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.TextChannel):
            await ctx.send("Please select a valid text channel for announcement.")
            return

        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"contest_announcement_channel": channel.id}},
                upsert=True
            )
            await ctx.send(f"<#{channel.id}> is set as announcement channel")
        except Exception as e:
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_announcement_channel", description="Get announcement channel")
    async def contest_get_announcement_channel(self, ctx: commands.Context):
        await ctx.defer()

        announcement_channel = await get_contest_announcement_channel(self.bot, guild_id=ctx.guild.id)
        if announcement_channel:
            await ctx.send(f"Announcement channel is set to <#{announcement_channel.id}>")
        else:
            await ctx.send("Announcement channel is not set.")


    @commands.hybrid_command(name="contest_set_ping_role", description="Select contest ping role")
    async def contest_set_ping_role(self, ctx: commands.Context, *, role: discord.Role = None):
        await ctx.defer()
        if role is None:
            await ctx.send("Please specify a role.")
            return
        if not isinstance(role, discord.Role):
            await ctx.send("Please select a valid role.")
            return
        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"contest_ping_role": role.id}},
                upsert=True
            )
            await ctx.send(f"{role.mention} is set as contest ping role")
        except Exception as e:
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_ping_role", description="Get contest ping role")
    async def contest_get_ping_role(self, ctx: commands.Context):
        await ctx.defer()

        ping_role = await get_contest_ping_role(self.bot, guild_id=ctx.guild.id)
        if ping_role:
            await ctx.send(f"Contest ping role is set to <@&{ping_role.id}>")
        else:
            await ctx.send("Contest ping role is not set.")


    @commands.hybrid_command(name="contest_set_archive_channel", description="Select art archive channel")
    async def contest_set_archive_channel(self, ctx: commands.Context, *, channel: discord.ForumChannel = None):
        await ctx.defer()
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.ForumChannel):
            await ctx.send("Please select a valid forum channel for art archive.")
            return

        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"contest_archive_channel": channel.id}},
                upsert=True)
            await ctx.send(f"<#{channel.id}> is set as art archive channel")
        except Exception as e:
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_archive_channel", description="Get archive channel")
    async def contest_get_archive_channel(self, ctx: commands.Context):
        await ctx.defer()

        archive_channel = await get_contest_archive_channel(self.bot, guild_id=ctx.guild.id)
        if archive_channel:
            await ctx.send(f"Archive channel is set to <#{archive_channel.id}>")
        else:
            await ctx.send("Archive channel is not set.")


    @commands.hybrid_command(name="contest_set_logs_channel", description="Select bot log channel")
    async def contest_set_logs_channel(self, ctx: commands.Context, *, channel: discord.TextChannel = None):
        await ctx.defer()
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.TextChannel):
            await ctx.send("Please select a valid text channel for bot log.")
            return

        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"contest_logs_channel": channel.id}},
                upsert=True)
            await ctx.send(f"<#{channel.id}> is set as bot log channel")
        except Exception as e:
            await ctx.send(f"Error: {e}")


    @commands.hybrid_command(name="contest_get_logs_channel", description="Get logs channel")
    async def get_logs_channel(self, ctx: commands.Context):
        await ctx.defer()

        logs_channel = await get_logs_channel(self.bot, guild_id=ctx.guild.id)
        if logs_channel:
            await ctx.send(f"Logs channel is set to <#{logs_channel.id}>")
        else:
            await ctx.send("Logs channel is not set.")

    @commands.hybrid_command(name="contest_create_channel", description="Create contest channel")
    async def contest_create_channel(self, ctx: commands.Context):
        await ctx.defer()
        guild = ctx.guild

        bot_member = guild.me
        server_config = await self.collection.find_one({"_id": guild.id})

        default_overwrites = {
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False
            )
        }

        contest_category = discord.utils.get(guild.categories, name="Contest")
        if contest_category is None:
            try:
                contest_category = await guild.create_category("Contest")
                await contest_category.set_permissions(bot_member, overwrite=default_overwrites[bot_member])
                await contest_category.set_permissions(guild.default_role, overwrite=default_overwrites[guild.default_role])
            except discord.Forbidden:
                print(f"Bot does not have permission to create category{discord.Forbidden}")
                return
        try:
            await contest_category.set_permissions(
                bot_member,
                overwrite=discord.PermissionOverwrite(
                    manage_channels=True,
                    view_channel=True,
                    send_messages=True,
                    manage_threads=True,
                    read_message_history=True
                )
            )
        except Exception as e:
            print(f"Could not update category permissions for bot: {e}")

        contest_role = guild.get_role(server_config.get("contest_role")) if server_config else None
        print(f"Contest role: {contest_role}")

        view_only_overwrite = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False
            )
        }

        print(f"View only overwrite: {view_only_overwrite}")

        async def get_or_create_role(name):
            return discord.utils.get(guild.roles, name=name) or await guild.create_role(name=name)

        ping_role = await get_or_create_role("Contest Ping")

        async def get_or_create_channel(name, cls, reason, extra_overwrite=None,
                                        inactivity_timeout=None):
            existing = discord.utils.get(guild.channels, name=name)
            if existing:
                return existing

            overwrites = {**default_overwrites}

            if extra_overwrite:
                for role, perms in extra_overwrite.items():
                    if isinstance(role, discord.Role) and role.position >= guild.me.top_role.position:
                        print(f"⚠️ Skipping overwrite for {role.name} due to role hierarchy (bot role too low).")
                        continue
                    overwrites[role] = perms

            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                send_messages=True,
                manage_threads=True,
                read_message_history=True
            )

            try:
                if cls == discord.TextChannel:
                    return await guild.create_text_channel(
                        name,
                        category=contest_category,
                        reason=reason,
                        overwrites=overwrites,
                    )

                elif cls == discord.ForumChannel:
                    kwargs = {
                        "category": contest_category,
                        "reason": reason,
                        "default_layout": discord.ForumLayoutType.gallery_view,
                        "overwrites": overwrites
                    }
                    if inactivity_timeout:
                        kwargs["default_auto_archive_duration"] = inactivity_timeout
                    return await guild.create_forum(name, **kwargs)
                return None

            except discord.Forbidden:
                print(
                    f"Bot does not have permission to create {cls.__name__}: Missing permissions or role hierarchy issue.")
                return None

        submission_channel = await get_or_create_channel("contest-submit", discord.TextChannel, "Submission channel")
        voting_channel = await get_or_create_channel("contest-vote", discord.ForumChannel, "Voting channel",
                                                     inactivity_timeout=10080)
        announcement_channel = await get_or_create_channel("contest-announcement", discord.TextChannel,
                                                           "Announcement channel", extra_overwrite=view_only_overwrite)
        contest_archive_channel = await get_or_create_channel("contest-archive", discord.ForumChannel,
                                                              "Contest archive channel")
        logs_channel = await get_or_create_channel("bot-logs", discord.TextChannel, "Bot log channel")

        try:
            await self.collection.update_one(
                {"_id": ctx.guild.id},
                {"$set": {
                    "submission_channel": submission_channel.id,
                    "voting_channel": voting_channel.id,
                    "contest_announcement_channel": announcement_channel.id,
                    "contest_archive_channel": contest_archive_channel.id,
                    "contest_logs_channel": logs_channel.id,
                    "contest_ping_role": ping_role.id
                }},
                upsert=True
            )
            await ctx.send("Contest channels created successfully.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
