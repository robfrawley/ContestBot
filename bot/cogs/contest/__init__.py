from bot.cogs.contest.base import ContestManager
from bot.cogs.contest.commands import ContestCommands
from bot.cogs.contest.reactions import ContestReactionsWatcher


async def setup(bot):
    cog = ContestManager(bot)
    await bot.add_cog(ContestManager(bot))
    await bot.add_cog(ContestCommands(bot))
    await bot.add_cog(ContestReactionsWatcher(bot))
    await cog.jobs.schedule_job()
