from collections import defaultdict
from typing import Optional

from .utils import fuzzy
from .utils.paginator import Embed, Pages

from discord.ext import commands, menus
import discord

class TagNotFound(Exception):
    def __init__(self, name, tags: Optional[tuple]):
        self.name = name
        self.tags = tags
    
    def __str__(self):
        if self.tags:
            total = 0
            for idx in range(len(self.tags[1])):
                total += len(self.tags[1][idx])
                if total > 1900:
                    self.tags = self.tags[1][:idx]
            
            if len(self.tags[1]):
                return f'Tag "{self.name}" not found. Did you mean...\n'+'\n'.join(tag for tag in self.tags[1])
        return f'Tag "{self.name}" not found.'


class TagName(commands.Converter):
    async def convert(self, ctx, argument: commands.clean_content):
        if len(argument) > 50:
            raise commands.BadArgument(f'{len(argument)} character tag name/alias is too long (50 character max).')
        
        root = ctx.bot.get_command('tag')
        if argument.split()[0] in root.all_commands:
            raise commands.BadArgument(f'{argument} tag name/alias starts with a reserved word.')
        return argument


class TagContent(commands.Converter):
    async def convert(self, ctx, argument: commands.clean_content):
        if len(argument) > 1000:
            raise commands.BadArgument(f'{len(argument)} character tag content is too long (1000 character max).')
        return argument


class TagPageSource(menus.ListPageSource):
    def __init__(self, tags, author, context):
        super().__init__(entries=sorted(tags, key=lambda t: t[0][0]), per_page=6)
        self.author = author
        self.context = context
    
    async def format_page(self, menu, entries):
        description = f'By {self.author}'
        embed = Embed(title=f'Tags by {self.author}', author=self.author, ctx=self.context)
        for tag in entries:
            embed.add_field(name=tag[0][0], value=tag[1], inline=False)
        
        max_pages = self.get_max_pages()
        if max_pages > 1:
            embed.set_footer(text=f'Page {menu.current_page + 1}/{max_pages}')
        return embed


class Tags(commands.Cog):
    """Tag related commands."""
    def __init__(self, bot):
        self.bot = bot
        self._tags = defaultdict(dict)
    
    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, *, name: TagName):
        """Allows you to tag text for later retrieval."""
        check = self._tags[ctx.guild.id]
        match = fuzzy.find(name, check)
        if not match[0]:
            raise TagNotFound(name, match)
        
        ref = ctx.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return await ref.resolved.reply(match[1][1])
        await ctx.reply(match[1][1])
    
    @tag.command(aliases=['add', 'make'])
    @commands.guild_only()
    async def create(self, ctx, name: TagName, *, content: TagContent):
        """Creates a new server-wide tag."""
        check = self._tags[ctx.guild.id]
        match = fuzzy.find(name, check)
        if match[0]:
            return await ctx.reply('This tag already exists.')
        
        try:
            self._tags[ctx.guild.id][ctx.author.id].append([[name], content, ctx.author])
        except KeyError:
            self._tags[ctx.guild.id][ctx.author.id] = [[[name], content, ctx.author]]
        await ctx.message.add_reaction('\N{THUMBS UP SIGN}')

    @tag.command()
    @commands.guild_only()
    async def alias(self, ctx, old_name: TagName, new_name: TagName):
        """Creates a server-wide alias for an already existing tag."""
        check = self._tags[ctx.guild.id]
        match = fuzzy.find(old_name, check)
        if not match[0]:
            raise TagNotFound(old_name, match)
        
        idx = check[match[2]].index(match[1])
        locale = self._tags[ctx.guild.id][match[2]][idx][0]

        if new_name not in locale:
            self._tags[ctx.guild.id][match[2]][idx][0].append(new_name)
        await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    @tag.command()
    @commands.guild_only()
    async def edit(self, ctx, name: TagName, new_content: TagContent):
        """Edits content for an already existing tag."""
        check = self._tags[ctx.guild.id]
        match = fuzzy.find(name, check)
        if not match[0]:
            raise TagNotFound(name, match)
        
        is_owner = (ctx.author.id == match[2])
        if not is_owner:
            raise commands.CheckFailure()
        
        idx = check[match[2]].index(match[1])
        self._tags[ctx.guild.id][match[2]][idx][1] = new_content
        await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    @tag.command(aliases=['remove'])
    @commands.guild_only()
    async def delete(self, ctx, name: TagName):
        """Deletes an already existing tag.
        
        To use this command, you must be the owner of the tag or have the Manage Server permission.
        """
        check = self._tags[ctx.guild.id]
        match = fuzzy.find(name, check)
        if not match[0]:
            raise TagNotFound(name, match)
        
        is_mod = ctx.channel.permissions_for(ctx.author).manage_guild
        is_owner = (ctx.author.id == match[2])
        if not (is_mod or is_owner):
            raise commands.CheckFailure()
        
        idx = check[match[2]].index(match[1])
        del self._tags[ctx.guild.id][match[2]][idx]
        await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    @tag.command()
    @commands.guild_only()
    async def transfer(self, ctx, name: TagName, mention: discord.Member):
        """Transfers ownership of an already existing tag.
        
        To use this command, you must be the owner of the tag.
        """
        check = self._tags[ctx.guild.id]
        match = fuzzy.find(name, check)
        if not match[0]:
            raise TagNotFound(name, match)
        
        is_owner = (ctx.author.id == match[2])
        if not is_owner:
            raise commands.CheckFailure()
        
        idx = check[match[2]].index(match[1])
        deleted = self._tags[ctx.guild.id][match[2]].pop(idx)
        
        try:
            self._tags[ctx.guild.id][mention.id].append(deleted)
        except KeyError:
            self._tags[ctx.guild.id][mention.id] = [deleted]
        await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    @commands.command()
    @commands.guild_only()
    async def tags(self, ctx, mention: Optional[discord.Member]):
        """Lists all (or at least most) of the tags owned by a member of the server."""
        if not mention:
            mention = ctx.author
        
        try:
            owned = self._tags[ctx.guild.id][mention.id]
            if not owned:
                raise KeyError
        except KeyError:
            return await ctx.reply(f'{mention} has no tags in this server.')
        
        total = last = 0
        for tag in owned:
            total += len(tag[0][0])+len(tag[1])
            last += 1
            if total > 5000 or last > 25:
                last = owned.index(tag)
                break
        
        owned = owned[:last]
        menu = Pages(TagPageSource(owned, mention, ctx), ctx)
        await menu.start(ctx)


def setup(bot):
    bot.add_cog(Tags(bot))
