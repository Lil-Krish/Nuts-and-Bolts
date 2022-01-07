import time

from .utils.paginator import Embed, Pages

from discord.ext import commands, menus

class HelpPageSource(menus.ListPageSource):
    def __init__(self, help_command, commands, context):
        super().__init__(entries=sorted(commands.keys(), key=lambda c: c.qualified_name), per_page=6)
        self.help_command = help_command
        self.commands = commands
        self.context = context
    
    async def format_page(self, menu, cogs):
        description = f'Use `?help [command]` for more information on a command group.'
        embed = Embed(title='Categories', description=description, ctx=self.context)
        
        for cog in cogs:
            commands = self.commands.get(cog)
            if commands:
                short_doc = cog.description.split('\n', 1)[0]+'\n'
                current_count = len(short_doc)

                page = []
                for command in commands:
                    form = f'`{command.name}`'
                    count = len(form)+2
                    if count + current_count < 900:
                        current_count += count
                        page.append(form)
                
                embed.add_field(name=cog.qualified_name, value=short_doc + ' '.join(page), inline=True)
        
        max_pages = self.get_max_pages()
        if max_pages > 1:
            embed.set_footer(text=f'Page {menu.current_page + 1}/{max_pages}')
        return embed


class GroupPageSource(menus.ListPageSource):
    def __init__(self, group, commands, context):
        super().__init__(entries=commands, per_page=6)
        self.group = group
        self.title = f'{self.group.qualified_name} Commands'
        self.description = self.group.description
        self.context = context
    
    async def format_page(self, menu, commands):
        embed = Embed(title=self.title, description=self.description, ctx=self.context)
        
        for command in commands:
            signature = f'{command.qualified_name} {command.signature}'
            embed.add_field(name=signature, value=command.short_doc, inline=False)
        
        embed.set_footer(text=f'Use ?help [command] for more info on a command')
        return embed


class Help(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Shows help about a command or category.'
        })
    
    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            names = f'[{command.name}|{aliases}]'
            if parent:
                names = f'{parent} {names}'
            aliases = names
        else:
            aliases = command.name if not parent else f'{parent} {command.name}'
        return f'{aliases} {command.signature}'
    
    async def send_bot_help(self, mapping):
        bot = self.context.bot
        entries = await self.filter_commands(bot.commands, sort=True)

        all_commands = {}
        for command in entries:
            if command.cog is None:
                continue
            try:
                all_commands[command.cog].append(command)
            except KeyError:
                all_commands[command.cog] = [command]

        menu = Pages(HelpPageSource(self, all_commands, self.context), self.context)
        await menu.start(self.context)
    
    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        
        menu = Pages(GroupPageSource(cog, entries, self.context), self.context)
        await menu.start(self.context)
    
    async def send_group_help(self, group):
        sub = group.commands
        if len(sub) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(sub, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupPageSource(group, entries, self.context)
        source.title = self.get_command_signature(group)
        source.description = group.help

        menu = Pages(source, self.context)
        await menu.start(self.context)
    
    async def send_command_help(self, command):
        embed = Embed(ctx=self.context)
        embed.title = self.get_command_signature(command)
        embed.description = command.help
        embed.set_footer(text='Use ?help to view a list of all commands.')
        await self.context.send(embed=embed)


class Meta(commands.Cog):
    """Handles utilities related to the bot itself."""
    def __init__(self, bot):
        self.bot = bot
        bot.help_command = Help()
        bot.help_command.cog = self
    
    @commands.command()
    async def ping(self, ctx):
        """Replies with the bot latency."""
        timing = round(1000*self.bot.latency, 2)
        await ctx.reply(f'Pong. ({timing} ms)')
    
    @commands.Cog.listener()
    async def on_connect(self):
        self.bot.then = round(time.time())
    
    @commands.command(aliases=['up'])
    async def uptime(self, ctx):
        """Replies with how long the bot has been up for."""
        interval = time.gmtime(round(time.time()) - self.bot.then)
        hrs, mins, secs = int(time.strftime('%H', interval)), int(time.strftime('%M', interval)), int(time.strftime('%S', interval))
        
        attrs = {
            'h' : ('', str(hrs)+' hour, ', str(hrs)+' hours, '),
            'm' : ('', str(mins)+' minute, ', str(mins)+' minutes, '),
            's' : ('', str(secs)+' second, ', str(secs)+' seconds, '),
        }
        
        uptime = f"{attrs['h'][(hrs, 2)[hrs > 1]]}{attrs['m'][(mins, 2)[mins > 1]]}{attrs['s'][(secs, 2)[secs > 1]]}"[:-2]
        await ctx.reply(f"{uptime}.")


def setup(bot):
    bot.add_cog(Meta(bot))
