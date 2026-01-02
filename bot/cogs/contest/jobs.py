import os
from datetime import datetime
from pathlib import Path
from bot.config import settings, logger

import discord
from dataclasses import dataclass, field
from typing import List, Tuple

from bot.cogs.contest.utils import get_submission_channel, get_contest_role, get_voting_channel, \
    get_contest_announcement_channel, get_contest_ping_role, get_contest_archive_channel, get_discord_file_from_url, \
    get_logs_channel, build_discord_embed_with_role_ping, build_discord_embed_with_thumbnail_and_role_ping, \
    find_first_image_post_for_forum_thread, roll_with_rerolls, build_discord_embed_with_thumbnail_and_image_and_role_ping, Winner
from bot.core.error_embed import create_logs_embed


class ContestJobs:
    def __init__(self, cog):
        self.cog = cog
        self.bot = self.cog.bot
        self.collection = self.bot.db["ServerConfig"]
        self.submissions_collection = self.bot.db["submissions"]

    async def schedule_job(self):
        scheduler = self.bot.scheduler
        async for config in self.collection.find({}):
            guild_id = config["_id"]

            scheduler.add_job(
                self.open_submission_channel, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_show_submit_channel.day,
                hour=settings.schedule_show_submit_channel.hour,
                minute=settings.schedule_show_submit_channel.minute,
                second=settings.schedule_show_submit_channel.second,
                timezone=settings.bot_timezone,
            )
            scheduler.add_job(
                self.close_submission_channel, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_hide_submit_channel.day,
                hour=settings.schedule_hide_submit_channel.hour,
                minute=settings.schedule_hide_submit_channel.minute,
                second=settings.schedule_hide_submit_channel.second,
                timezone=settings.bot_timezone,
            )
            scheduler.add_job(
                self.post_submission_to_forum, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_make_voting_forum.day,
                hour=settings.schedule_make_voting_forum.hour,
                minute=settings.schedule_make_voting_forum.minute,
                second=settings.schedule_make_voting_forum.second,
                timezone=settings.bot_timezone,
            )
            scheduler.add_job(
                self.open_voting_channel, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_show_voting_forum.day,
                hour=settings.schedule_show_voting_forum.hour,
                minute=settings.schedule_show_voting_forum.minute,
                second=settings.schedule_show_voting_forum.second,
                timezone=settings.bot_timezone,
            )
            scheduler.add_job(
                self.close_voting_channel, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_hide_voting_forum.day,
                hour=settings.schedule_hide_voting_forum.hour,
                minute=settings.schedule_hide_voting_forum.minute,
                second=settings.schedule_hide_voting_forum.second,
                timezone=settings.bot_timezone,
            )
            scheduler.add_job(
                self.announce_winner, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_annc_winner.day,
                hour=settings.schedule_annc_winner.hour,
                minute=settings.schedule_annc_winner.minute,
                second=settings.schedule_annc_winner.second,
                timezone=settings.bot_timezone,
            )
            scheduler.add_job(
                self.close_contest, "cron", kwargs={"guild_id": guild_id},
                day=settings.schedule_ends_events.day,
                hour=settings.schedule_ends_events.hour,
                minute=settings.schedule_ends_events.minute,
                second=settings.schedule_ends_events.second,
                timezone=settings.bot_timezone
            )


    async def open_submission_channel(self, guild_id: int = None):
        submission_channel = await get_submission_channel(self.bot, guild_id= guild_id)
        member = await get_contest_role(self.bot, guild_id= guild_id)
        logs_channel = await get_logs_channel(self.bot, guild_id= guild_id)

        logger.info(f"Opening submission channel \"{submission_channel}\" for guild \"{guild_id}\"")

        if submission_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Submission channel Not Found",
                        description=f"Submission channel not found When opening the submission channel.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Submission channel not set.")
            return

        if member is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Contest Role Not Found",
                        description=f"Contest role not found when opening the submission channel. Make sure to set the contest role using the `contest_role` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Contest role not set.")
            return

        if submission_channel and isinstance(submission_channel, discord.TextChannel) and member:
            overwrites = discord.PermissionOverwrite()
            overwrites.send_messages = True
            overwrites.view_channel = True
            overwrites.read_message_history = False
            overwrites.attach_files = True
            try:
                await submission_channel.set_permissions(member, overwrite=overwrites)
            except discord.Forbidden:
                logger.warn("Bot does not have permission to set permissions in the submission channel.")
                return

        announcement_channel = await  get_contest_announcement_channel(self.bot, guild_id= guild_id)
        contest_ping_role = await get_contest_ping_role(self.bot, guild_id=guild_id)
        logger.debug(f"Contest ping role: {contest_ping_role}")
        if announcement_channel is not None:
            await announcement_channel.send(
                **build_discord_embed_with_role_ping(
                    title="Submissions Channel Opened",
                    description=(
                        f"The contest submission channel is now open! Submit your entries by posting a single image in <#{submission_channel.id}>."
                        f"\n\n"
                        f"If you want to change your submission, submit another message with a new image in that channel; "
                        f"this will overwrite your previous entry."
                        f"\n\n"
                        f"**Good luck to all participants!**"
                    ),
                    roles=contest_ping_role,
                    color=discord.Color.green()
                )
            )

        if submission_channel is not None:
            await submission_channel.send(
                **build_discord_embed_with_role_ping(
                    title="Submit Contest Entries Here",
                    description=(
                        f"Submit your contest entries by posting them in this channel! Only single-image posts are allowed."
                        f"\n\n"
                        f"**Good luck to all participants!**"
                    ),
                    roles=contest_ping_role,
                    color=discord.Color.green()
                )
            )

        logger.info(f"Opened submission channel at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


    async def close_submission_channel(self, guild_id: int = None):
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)
        submission_channel = await get_submission_channel(self.bot, guild_id=guild_id)
        member = await get_contest_role(self.bot, guild_id= guild_id)

        logger.info(f"Closing submission channel \"{submission_channel}\" for guild \"{guild_id}\"")

        if submission_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Submission channel Not Found",
                        description=f"Submission channel not found When closing the submission channel.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Submission channel not set.")
            return

        if member is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Contest Role Not Found",
                        description=f"Contest role not found When closing the submission channel. Make sure to set the contest role using the `contest_role` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Contest role not set.")
            return

        if submission_channel and isinstance(submission_channel, discord.TextChannel) and member:
            overwrites = discord.PermissionOverwrite()
            overwrites.view_channel = False
            overwrites.read_message_history = False
            await submission_channel.set_permissions(member, overwrite=overwrites)

        announcement_channel = await  get_contest_announcement_channel(self.bot, guild_id=guild_id)
        contest_ping_role = await get_contest_ping_role(self.bot, guild_id=guild_id)
        logger.debug(f"Contest ping role: {contest_ping_role}")
        if announcement_channel is not None:
            await announcement_channel.send(
                **build_discord_embed_with_role_ping(
                    title="Submissions Channel Closed",
                    description=(
                        f"The submission channel is now closed! Submissions are no longer being accepted. Check back soon for voting details."
                    ),
                    roles=contest_ping_role,
                    color=discord.Color.red()
                )
            )

        logger.info(f"Closed submission channel at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


    async def post_submission_to_forum(self, guild_id: int = None,):
        guild = self.bot.get_guild(guild_id)
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)

        logger.info(f"Post submission to forum for guild \"{guild_id}\"")

        if guild is None:
            logger.warn("Guild not found.")
            return None

        voting_channel = await get_voting_channel(self.bot, guild_id= guild_id)
        if voting_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Voting Channel Not Found",
                        description=f"Voting channel not found When posting submissions to the forum. Make sure to set the voting channel using the `contest_voting_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Voting channel not set.")

        current_month = datetime.now(settings.bot_timezone).strftime("%Y-%m")
        submissions = self.submissions_collection.find({
            "month": current_month,
            "guild_id": guild_id  
        })

        member = await get_contest_role(self.bot, guild_id= guild_id)
        if member is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Contest Role Not Found",
                        description=f"Contest role not found When posting submissions to the forum. Make sure to set the contest role using the `contest_role` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Contest role not set.")
            return None

        async for entry in submissions:
            user = guild.get_member(entry["user_id"])
            if not user:
                continue

            file_path = os.path.normpath(entry["file_path"])

            if not os.path.exists(file_path):
                logger.warn(f"File not found at {file_path}")
                continue

            file = discord.File(file_path, filename="submission.webp")

            thread = await voting_channel.create_thread(
                name=f"{user.display_name}'s Submission",
                content=f" ",
                file=file
            )

            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Submission Posted to Forum",
                        description=f"Submission posted to the forum by {user.mention}.",
                        color=discord.Color.green(),
                        thumbnails=user.avatar.url
                    )
                )

            try:
                await thread.message.add_reaction("🏆")
            except Exception as e:
                logger.warn(f"Error reacting to submission: {e}")

            await self.submissions_collection.update_one(
                {"_id": entry["_id"]},
                {"$set": {"thread_id": thread.message.id}}
            )
        return None


    async def open_voting_channel(self, guild_id: int = None,):
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)
        voting_channel = await get_voting_channel(self.bot, guild_id= guild_id)
        announcement_channel = await get_contest_announcement_channel(self.bot, guild_id= guild_id)
        contest_ping_role = await get_contest_ping_role(self.bot, guild_id=guild_id)

        logger.info(f"Opening voting channel \"{voting_channel}\" for guild \"{guild_id}\"")

        if voting_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Voting Channel Not Found",
                        description=f"Voting channel not found When opening the voting channel. Make sure to set the voting channel using the `contest_voting_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Voting channel not set.")
            return
        member = await get_contest_role(self.bot, guild_id= guild_id)
        if member is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Contest Role Not Found",
                        description=f"Contest role not found When opening the voting channel. Make sure to set the contest role using the `contest_role` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Contest role not set.")
            return

        if voting_channel and isinstance(voting_channel, discord.ForumChannel) and member:
            overwrites = discord.PermissionOverwrite()
            overwrites.view_channel = True
            overwrites.send_messages =False
            overwrites.read_message_history = True
            try:
                await voting_channel.set_permissions(target=member, overwrite=overwrites)
                await announcement_channel.send(
                    **build_discord_embed_with_role_ping(
                        title="Voting Channel Opened",
                        description=(
                            f"The voting channel is now open! Take a moment to browser through the contest entries in <#{voting_channel.id}> "
                            f"and upvote your favorite submissions by reacting to the forum posts with the trophy emoji."
                            f"\n\n"
                            f"Share your thoughts and talk with other members about specific entries in their dedicated forum post threads. "
                            f"And don't forget to vote on your own submission, too!"
                            f"\n\n"
                            f"**Good luck to all participants!**"
                        ),
                        roles=contest_ping_role,
                        color=discord.Color.green()
                    )
                )
            except discord.Forbidden:
                if logs_channel:
                    await logs_channel.send(
                        embed=create_logs_embed(
                            title="Bot Does Not Have Permission to Set Permissions in the Voting Channel",
                            description=f"Bot does not have permission to set permissions in the voting channel. Make sure the bot has the `manage_channels` permission in the voting channel.",
                            color=discord.Color.red()
                        )
                    )
                logger.warn("Bot does not have permission to set permissions in the voting channel.")
                return


    async def close_voting_channel(self, guild_id: int = None,):
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)
        voting_channel = await get_voting_channel(self.bot, guild_id= guild_id)

        logger.info(f"Closing voting channel \"{voting_channel}\" for guild \"{guild_id}\"")

        if voting_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Voting Channel Not Found",
                        description=f"Voting channel not found When closing the voting channel. Make sure to set the voting channel using the `contest_voting_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Voting channel not set.")
            return
        member = await get_contest_role(self.bot, guild_id= guild_id)
        if member is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Contest Role Not Found",
                        description=f"Contest role not found When closing the voting channel. Make sure to set the contest role using the `contest_role` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Contest role not set.")
            return

        if voting_channel and isinstance(voting_channel, discord.ForumChannel) and member:
            overwrites = discord.PermissionOverwrite()
            overwrites.view_channel = False
            overwrites.read_message_history = False
            try:
                await voting_channel.set_permissions(target=member, overwrite=overwrites)
                announcement_channel = await  get_contest_announcement_channel(self.bot, guild_id=guild_id)
                contest_ping_role = await get_contest_ping_role(self.bot, guild_id=guild_id)
                if announcement_channel is not None:
                    await announcement_channel.send(
                        **build_discord_embed_with_role_ping(
                            title="Voting Channel Closed",
                            description=(
                                f"The voting channel is now closed. Thank you for participating! A winner will be announced soon."
                            ),
                            roles=contest_ping_role,
                            color=discord.Color.green()
                        )
                    )
            except discord.Forbidden:
                if logs_channel:
                    await logs_channel.send(
                        embed=create_logs_embed(
                            title="Bot Does Not Have Permission to Set Permissions in the Voting Channel",
                            description=f"Bot does not have permission to set permissions in the voting channel. Make sure the bot has the `manage_channels` permission in the voting channel.",
                            color=discord.Color.red()
                        )
                    )
                logger.warn("Bot does not have permission to set permissions in the voting channel.")


    async def announce_winner(self, guild_id: int = None,):
        guild = self.bot.get_guild(guild_id)
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)

        logger.info(f"Posting winner for guild \"{guild_id}\"")

        if guild is None:
            logger.warn("Guild not found.")
            return None

        voting_channel = await get_voting_channel(self.bot, guild_id= guild_id)
        if voting_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Voting Channel Not Found",
                        description=f"Voting channel not found When announcing the winner. Make sure to set the voting channel using the `contest_voting_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Voting channel not set.")
            return None

        announcement_channel = await get_contest_announcement_channel(self.bot, guild_id= guild_id)
        if announcement_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Announcement Channel Not Found",
                        description=f"Announcement channel not found When announcing the winner. Make sure to set the announcement channel using the `contest_announcement_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Announcement channel not set.")
            return None

        now = datetime.now(settings.bot_timezone)
        current_month = now.month
        current_year = now.year

        current_winner: Winner | None = None
        top_votes = 0

        for thread in voting_channel.threads:
            # Only consider threads from the current month/year
            if thread.created_at.month != current_month or thread.created_at.year != current_year:
                continue

            # Find the first image post in the thread
            image_message = await find_first_image_post_for_forum_thread(thread)
            if not image_message or not image_message.attachments:
                continue

            # Count votes
            vote_count = sum(r.count for r in image_message.reactions)

            # Pick the first valid image attachment
            attachment = next(
                a for a in image_message.attachments
                if a.content_type and a.content_type.startswith("image/")
            )

            # Skip posts with 1 or fewer votes
            if vote_count <= 1:
                continue

            # Create a candidate Winner object
            candidate = Winner(
                bot=self.bot,
                thread=thread,
                user=image_message.author,
                attachment=attachment,
                votes=vote_count,
            )
            await candidate.async_init(guild, self.submissions_collection)
            logger.debug(f"Evaluating candidate: {candidate.thread_id}/{candidate.user_mention} ({vote_count} votes, roll {candidate.current_roll})")

            # First valid winner
            if current_winner is None:
                current_winner = candidate
                top_votes = vote_count
                logger.debug(
                    f"Initial winner {candidate.thread_id} ({vote_count} votes, roll {candidate.current_roll})"
                )
                continue

            # More votes always wins
            if vote_count > top_votes:
                current_winner = candidate
                top_votes = vote_count
                logger.debug(
                    f"New winner by votes: {candidate.thread_id} ({vote_count} votes)"
                )
                continue

            # Tie → use dice rolls as tiebreaker
            if vote_count == top_votes:
                cw = current_winner

                if announcement_channel is not None:
                    await announcement_channel.send(
                        **build_discord_embed_with_role_ping(
                            title="Vote Tie Detected: Rolling Two D10 Dice Each 🎲",
                            description=(
                                f"A tie in votes was detected! Dice rolls will decide the winner.\n\n"
                                f"**Incumbent:** ({cw.user_mention})\n"
                                f"• Rolls: {cw.current_roll[0]} + {cw.current_roll[1]} (2D10)\n"
                                f"• Total: **{cw.roll_total}**\n\n"
                                f"**Challenger:** ({candidate.user_mention})\n"
                                f"• Rolls: {candidate.current_roll[0]} + {candidate.current_roll[1]} (2D10)\n"
                                f"• Total: **{candidate.roll_total}**"
                            ),
                            roles=[cw.user_mention, candidate.user_mention],
                            color=discord.Color.gold()
                        )
                    )

                if candidate.roll_total == cw.roll_total:
                    # Perfect tie → reroll

                    logger.debug(f"Perfect tie detected; current role: {candidate.rolls} vs {cw.rolls}")
                    roll_with_rerolls(candidate, True)
                    roll_with_rerolls(cw, True)
                    logger.debug(f"Perfect tie detected; reroll: {candidate.rolls} vs {cw.rolls}")

                    if announcement_channel is not None:
                        await announcement_channel.send(
                            **build_discord_embed_with_role_ping(
                                title="Perfect Tie Detected: Rerolling Dice 🎲",
                                description=(
                                    f"A perfect tie was detected! Rerolling the dice to determine the winner.\n\n"
                                    f"**Incumbent:** ({cw.user_mention})\n"
                                    f"• Rolls: {cw.current_roll[0]} + {cw.current_roll[1]} (2D10)\n"
                                    f"• Total: **{cw.roll_total}**\n\n"
                                    f"**Challenger:** ({candidate.user_mention})\n"
                                    f"• Rolls: {candidate.current_roll[0]} + {candidate.current_roll[1]} (2D10)\n"
                                    f"• Total: **{candidate.roll_total}**"
                                ),
                                roles=[cw.user_mention, candidate.user_mention],
                                color=discord.Color.orange()
                            )
                        )

                if candidate.roll_total > cw.roll_total:
                    current_winner = candidate
                    if announcement_channel is not None:
                        await announcement_channel.send(
                            **build_discord_embed_with_role_ping(
                                title="Tiebreak Winner Determined 🏆",
                                description=(
                                    f"The challenger has won the tiebreak!\n\n"
                                    f"**Winning Thread:** {candidate.thread.name}\n"
                                    f"**Winner:** {candidate.user_mention}\n"
                                    f"**Dice Total:** {candidate.roll_total} (vs {cw.roll_total})"
                                ),
                                roles=[candidate.user_mention],
                                color=discord.Color.green()
                            )
                        )
                else:
                    if announcement_channel is not None:
                        await announcement_channel.send(
                            **build_discord_embed_with_role_ping(
                                title="Tiebreak Winner Determined 🏆",
                                description=(
                                    f"The incumbent remains the winner after the tiebreak.\n\n"
                                    f"**Winning Thread:** {cw.thread.name}\n"
                                    f"**Winner:** {cw.user_mention}\n"
                                    f"**Dice Total:** {cw.roll_total} (vs {candidate.roll_total})"
                                ),
                                roles=[cw.user_mention],
                                color=discord.Color.blue()
                            )
                        )

        logger.debug(f"Selected winner: {current_winner}")

        if not current_winner:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="No Winner Found",
                        description=f"No winner found in the voting channel.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("No winner found.")
            return None

        contest_ping_role = await get_contest_ping_role(self.bot, guild_id=guild_id)
        logger.debug(f"Contest ping role: {contest_ping_role}")
        if contest_ping_role is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Contest Ping Role Not Found",
                        description=f"Contest ping role not found When announcing the winner. Make sure to set the contest ping role using the `contest_ping_role` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Contest ping role not set.")

        logger.info(f"Announcing winner: {current_winner.user_display_name}/{current_winner.user_mention} with {current_winner.votes} votes.")

        await announcement_channel.send(
            **build_discord_embed_with_thumbnail_and_image_and_role_ping(
                title=f"Winner: {current_winner.user_display_name}",
                description=(
                    f"{current_winner.user_mention} has won the art contest with {current_winner.votes} votes! Congratulations!"
                ),
                roles=[contest_ping_role, current_winner.user_mention],
                thumbnail_url=current_winner.user.avatar.url if current_winner.user.avatar else None,
                image_url=current_winner.attachment.url if current_winner.attachment else None,
                color=discord.Color.green()
            )
        )

        if logs_channel:
            await logs_channel.send(
                embed = create_logs_embed(
                    title="Winner Announced",
                    description=f"Winner announced in the voting channel: {current_winner.user_mention}.",
                    color=discord.Color.green(),
                    thumbnails=current_winner.user.avatar.url if current_winner.user.avatar else None
                )
            )

        return None


    async def close_contest(self, guild_id: int = None,):
        guild = self.bot.get_guild(guild_id)
        logs_channel = await get_logs_channel(self.bot, guild_id=guild_id)
        voting_channel = await get_voting_channel(self.bot, guild_id= guild_id)
        art_archive_channel = await get_contest_archive_channel(self.bot, guild_id= guild_id)

        logger.info(f"Closing contest and archiving to \"{art_archive_channel}\" for guild \"{guild_id}\"")

        if voting_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Voting Channel Not Found",
                        description=f"Voting channel not found When closing the contest. Make sure to set the voting channel using the `contest_voting_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Voting channel not set.")
            return
        if art_archive_channel is None:
            if logs_channel:
                await logs_channel.send(
                    embed = create_logs_embed(
                        title="Art Archive Channel Not Found",
                        description=f"Art archive channel not found When closing the contest. Make sure to set the art archive channel using the `contest_archive_channel` command.",
                        color=discord.Color.red()
                    )
                )
            logger.warn("Art archive channel not set.")
            return
        threads = voting_channel.threads
        logger.info(f"Archiving {len(threads)} threads...")
        for thread in threads:
            try:
                if art_archive_channel is None:
                    continue

                user_data = await self.submissions_collection.find_one({"thread_id": thread.id})
                user = guild.get_member(user_data["user_id"])

                async for msg in thread.history(limit=1, oldest_first=True):
                    if msg.attachments:
                        attachment = msg.attachments[0]
                        file  = await get_discord_file_from_url(attachment.url ,attachment.filename)
                        await art_archive_channel.create_thread(
                            name=f"{user.display_name}'s Art Submission",
                            content=f"{user.display_name} \nTotal votes: {sum(r.count for r in msg.reactions)}",
                            file= file,
                            reason=f"Archived from the {voting_channel.name} contest."
                        )



                        guild_folder  = Path(f"bot/data/submissions/{guild_id}")
                        if guild_folder.exists():
                            for file in guild_folder.iterdir():
                                try:
                                    file.unlink()
                                    logger.debug(f"Deleted {file}")
                                except Exception as e:
                                    logger.warn(f"Error deleting {file}: {e}")
                        else:
                            logger.warn(f"No guild folder found for {guild_id}")

                await thread.delete()
                logger.info(f"Deleted thread {thread.name}")
            except Exception as e:
                if logs_channel:
                    await logs_channel.send(
                        embed = create_logs_embed(
                            title="Error Archiving Thread",
                            description=f"Error archiving thread {thread.name}: {e}",
                            color=discord.Color.red()
                        )
                    )
                logger.warn(f"Error archiving thread {thread.name}: {e}")


