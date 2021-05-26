import os, dotenv
from discord.ext import commands
import discord

initial_extensions = {
    'cogs.meta.meta',
    'cogs.tags.tags'
}

class AlphaCore(commands.Bot):
    def __init__(self):
        dotenv.load_dotenv()
        
        intents = discord.Intents.all()
        activity = discord.Activity(type=discord.ActivityType.watching, name="for ?help")
        
        super().__init__(command_prefix='?', activity=activity, intents=intents)
        
        for extension in initial_extensions:
            self.load_extension(extension)

    def run(self):
        super().run(os.getenv('TOKEN'), reconnect=True)

def main():
    bot = AlphaCore()
    bot.run()

if __name__ == '__main__':
    main()
