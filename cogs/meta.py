import os, time, dotenv
import discord
from discord.ext import commands

class Meta(commands.Cog):
    def __init__(self, bot):
        dotenv.load_dotenv()
        self.bot = bot
    
    @commands.command(brief='Displays the intro message.', description='Displays the intro message, including the bot developer and time zone.')
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def hello(self, ctx):
        owner = self.bot.get_user(int(os.getenv('owner')))
        await ctx.send(f'Hello! I\'m a robot! {owner.name}#{owner.discriminator} made me. Use `?help [command]` to learn what I can do! I record all timestamps in EST.')
    
    @commands.command(brief='Replies with the bot latency.', description='Replies with "Pong." and checks the latency of the bot. This command has a five second cooldown per member.')
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def ping(self, ctx):
        timing = round(round(self.bot.latency, 10) * 1000, 2)
        await ctx.send(f'Pong. ({timing} ms)')
    
    @commands.command(brief='Requests the developer to fix or add a feature to the bot.', description='Sends your suggestion to the bot developer. Only use this to notify the creator of an issue or to suggest a new feature. Misuse will lead to a blacklist. This command has a one minute cooldown per member.')
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def suggest(self, ctx, *, suggestion: str):
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
