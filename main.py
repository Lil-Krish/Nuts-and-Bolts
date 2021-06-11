import toml
from discord.ext import commands
import discord

initial_extensions = {
    'cogs.meta',
    'cogs.mod'
}

class NutsandBolts(commands.AutoShardedBot):
    def __init__(self):
        self.intents = discord.Intents.all()
        self.activity = discord.Activity(type=discord.ActivityType.watching, name="for ?help")
        
        super().__init__(command_prefix='?', activity=self.activity, intents=self.intents)
        
        for extension in initial_extensions:
            self.load_extension(extension)
        
        self.closed = toml.load('closed.toml')
        
        self.owner_id, self.token = self.closed['owner_id'], self.closed['token']

    def run(self):
        super().run(self.token, reconnect=True)


def main():
    bot = NutsandBolts()
    bot.run()

if __name__ == '__main__':
    main()
