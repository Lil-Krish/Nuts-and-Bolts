import os, time, dotenv
from discord.ext import commands
import discord

class Meta(commands.Cog):
    def __init__(self, bot):
        dotenv.load_dotenv()
        self.bot = bot
    
    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def hello(self, ctx):
        """Displays the intro message."""

        owner = self.bot.get_user(int(os.getenv('owner')))
        await ctx.send(f'Hello! I\'m a robot! {owner.name}#{owner.discriminator} made me. Use `?help [command]` to learn what I can do! I record all timestamps in EST.')
    
    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def ping(self, ctx):
        """Replies with the bot latency."""

        timing = round(round(self.bot.latency, 10) * 1000, 2)
        await ctx.send(f'Pong. ({timing} ms)')
    
    @commands.command()
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def suggest(self, ctx, *, suggestion: str):
        """Requests the developer to fix or add a feature to the bot.
        
        Please only use this command for the above purpose. 
        Misuse will lead to a blacklist.
        """


        author = await ctx.author.create_dm()
        owner = await self.bot.get_user(os.get_env('owner')).create_dm()

        await owner.send(f'{ctx.author.name}#{ctx.author.discriminator} suggested "{suggestion}".')
        await author.send('Your suggestion has been recorded.')
    
    @commands.Cog.listener()
    async def on_connect(self):
        self.bot.then = int(round(time.time()))
        
    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def uptime(self, ctx):
        """Replies with how long the bot has been up for."""

        interval = time.gmtime(int(round(time.time())) - self.bot.then)

        hrs, mins, secs = int(time.strftime('%H', interval)), int(time.strftime('%M', interval)), int(time.strftime('%S', interval))
        
        attrs = {
            'h' : ('', str(hrs)+' hour, ', str(hrs)+' hours, '),
            'm' : ('', str(mins)+' minute, ', str(mins)+' minutes, '),
            's' : ('', str(secs)+' second, ', str(secs)+' seconds, '),
        }
        
        uptime = f"{attrs['h'][(hrs, 2)[hrs > 1]]}{attrs['m'][(mins, 2)[mins > 1]]}{attrs['s'][(secs, 2)[secs > 1]]}"[:-2]
        
        await ctx.send('Uptime: **'+uptime+'**.')
    
def setup(bot):
    bot.add_cog(Meta(bot))
