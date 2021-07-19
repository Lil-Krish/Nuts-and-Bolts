import random
from typing import Optional

from discord.ext import commands

class RNG(commands.Cog):
    """(Pseudo) RNG commands."""

    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def choose(self, ctx, number: Optional[int] = 1, *choices: commands.clean_content):
        """Selects elements out of a list of choices."""
        await ctx.reply(' '.join(random.sample(choices, number)))
    
    @commands.command()
    async def generate(self, ctx, first_num: Optional[float] = 0, second_num: Optional[float] = 1):
        """Generates a random float within a bound."""
        await ctx.reply(round(random.uniform(first_num, second_num), 2))


def setup(bot):
    bot.add_cog(RNG(bot))
