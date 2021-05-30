from discord.ext import menus
import discord, asyncio

class Embed(discord.Embed):
    def __init__(self, **kwargs):
        self.title, self.description, self.ctx = kwargs.get('title', None), kwargs.get('description', None), kwargs.get('ctx')
        self.snowflake = 16775930

        self.colour = hash(self.ctx.author.roles[-1].colour) if self.ctx.guild else self.snowflake

        super().__init__(title=self.title, description=self.description, colour=self.colour)
        
        self.set_author(name=self.ctx.author.display_name, icon_url=self.ctx.author.avatar_url)


class Pages(menus.MenuPages):
    def __init__(self, source, context):
        super().__init__(source=source, check_embeds=True, clear_reactions_after=True)
        self.context = context

    @menus.button('\N{INFORMATION SOURCE}\ufe0f', position=menus.Last(3))
    async def info(self, payload):
        """Shows info about pagination."""

        embed = Embed(title='Pagnination Info', ctx=self.context)

        info = []
        for (emoji, button) in self.buttons.items():
            info.append(f'{emoji}: {button.action.__doc__}')

        embed.add_field(name='Function of Reactions', value='\n'.join(info), inline=False)
        embed.set_footer(text=f'We were on {self.current_page + 1}.')

        async def back():
            await asyncio.sleep(30.0)
            await self.show_page(self.current_page)

        self.bot.loop.create_task(back())
