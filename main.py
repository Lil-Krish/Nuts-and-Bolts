import os
from collections import defaultdict
from youtube_dl.utils import DownloadError

from discord.ext import commands
import discord

initial_extensions = {
    'cogs.api',
    'cogs.meta',
    'cogs.mod',
    'cogs.music',
    'cogs.rng',
    'cogs.tags',
}

class NutsandBolts(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        activity = discord.Activity(type=discord.ActivityType.watching, name="for ?help")
        super().__init__(command_prefix=commands.when_mentioned_or('?'), activity=activity, intents=intents)

        for extension in initial_extensions:
            self.load_extension(extension)
        
        self.owner_id, self.__token = os.environ['OWNER_ID'], os.environ['TOKEN']
        self.blocked = defaultdict(set)
    
    async def on_message(self, message):
        blocked = self.blocked['global'].copy()
        if message.guild:
            blocked.update(self.blocked[message.guild.id])
        
        if not (message.author.bot or message.author in blocked):
            await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.BadArgument):
            return await ctx.reply(error)
        if isinstance(error, commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.Forbidden):
                return await ctx.reply('The bot does not have permission to execute this command.')
            elif isinstance(original, discord.HTTPException):
                if isinstance(original, discord.NotFound):
                    return await ctx.reply('The requested entity was not found.')
                return await ctx.reply('An unexpected error occurred. Please try again later.')
            elif isinstance(original, DownloadError):
                return await ctx.reply('There was an error downloading the requested video.')
            else:
                return await ctx.reply(error.original)
        if isinstance(error, commands.CheckFailure):
            return await ctx.reply('You do not have permission to execute this command.')
        await ctx.reply(f'{error.__class__.__name__}: {error}')
    
    def run(self):
        super().run(self.__token, reconnect=True)


def main():
    bot = NutsandBolts()
    bot.run()

if __name__ == '__main__':
    main()
