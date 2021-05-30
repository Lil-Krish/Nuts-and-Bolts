import toml
from discord.ext import commands
import discord

initial_extensions = {
    'cogs.meta'
}

class NutsandBolts(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        activity = discord.Activity(type=discord.ActivityType.watching, name="for ?help")
        
        super().__init__(command_prefix='?', activity=activity, intents=intents)
        
        for extension in initial_extensions:
            self.load_extension(extension)
        
        self.token = toml.load('token.toml')['token']

    def run(self):
        super().run(self.token, reconnect=True)


def main():
    bot = NutsandBolts()
    bot.run()

if __name__ == '__main__':
    main()
