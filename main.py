import toml
from cogs.utils import checks
from discord.ext import commands
import discord

initial_extensions = {
    'cogs.meta',
    'cogs.mod'
}

class NutsandBolts(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        activity = discord.Activity(type=discord.ActivityType.watching, name="for ?help")
        
        super().__init__(command_prefix='?', activity=activity, intents=intents)
        
        for extension in initial_extensions:
            self.load_extension(extension)
        
        self.closed = toml.load('closed.toml')
        
        self.owner_id, self.token = self.closed['owner_id'], self.closed['token']

    async def on_command_error(self, ctx, error):
        await checks.error_handler(ctx, error)
    
    def run(self):
        super().run(self.token, reconnect=True)


def main():
    bot = NutsandBolts()
    bot.run()

if __name__ == '__main__':
    main()
