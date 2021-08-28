import asyncio
from typing import Optional

from discord.ext import menus
import discord

class Embed(discord.Embed):
    def __init__(self, **kwargs):
        title, description, ctx = kwargs.get('title', ''), kwargs.get('description', ''), kwargs['ctx']
        snowflake = 16775930
        
        colour = hash(kwargs.get('author', ctx.author).colour)
        if colour == hash(discord.Colour.default()):
            colour = snowflake
        
        super().__init__(title=title, description=description, colour=colour)
        
        self.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

    def add_field(self, name: Optional[str] = '\u200b', value: Optional[str] = '\u200b', inline: Optional[bool] = True):
        super().add_field(name=name, value=value, inline=inline)


class Pages(menus.MenuPages):
    def __init__(self, source, context):
        super().__init__(source=source, check_embeds=True, clear_reactions_after=True)
        self.context = context
    
    @menus.button('\N{INFORMATION SOURCE}\ufe0f', position=menus.Last(3))
    async def info(self, _):
        """Shows info about pagination."""
        embed = Embed(title='Pagnination Info', ctx=self.context)
        info = []
        for (emoji, button) in self.buttons.items():
            info.append(f'{emoji}: {button.action.__doc__.capitalize()}')

        embed.add_field(name='Reactions', value='\n'.join(info), inline=False)
        embed.set_footer(text=f'We were on page {self.current_page + 1}.')

        await self.message.edit(embed=embed)
        
        async def back():
            await asyncio.sleep(10.0)
            await self.show_page(self.current_page)

        self.bot.loop.create_task(back())
