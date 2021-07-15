from collections import defaultdict
from .utils import fuzzy
import discord
from discord.ext import commands

class Tags(commands.Cog):
    """Tag related commands."""

    def __init__(self, bot):
        self.bot = bot
        self._tags = defaultdict(dict)
    
    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, *, name: commands.clean_content):
        """Allows you to tag text for later retrieval."""
        
        check = self._tags[ctx.guild.id]
        if not check:
            return await ctx.reply("Tag not found.")
        
        match = fuzzy.find(name, check)

        if not match[0]:
            total = 0
            for idx in range(len(match[1])):
                total += len(match[1][idx])
                if total > 1900:
                    match = match[1][:idx]
            
            if len(match[1]):
                return await ctx.reply('Tag not found. Did you mean...\n'+'\n'.join(tag for tag in match[1]))
            await ctx.reply('Tag not found.')
        
        ref = ctx.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return await ref.resolved.reply(match[1][1])
        await ctx.reply(match[1][1])
    
    @tag.command(aliases=['add'])
    @commands.guild_only()
    async def create(self, ctx, name: commands.clean_content, *, content: commands.clean_content):
        """Creates a new server-wide tag."""

        if len(name) > 50:
            raise commands.BadArgument(f'{len(name)} character tag name is too long (50 character max).')

        root = self.bot.get_command('tag')
        if name.split()[0] in root.all_commands:
            raise commands.BadArgument('The name of this tag starts with a reserved word.')

        check = self._tags[ctx.guild.id]
        match = fuzzy.find(name, check)

        if match[0]:
            return await ctx.reply('This tag already exists.')

        try:
            self._tags[ctx.guild.id][ctx.author.id].append([[name], content, ctx.author])
        except KeyError:
            self._tags[ctx.guild.id][ctx.author.id] = [[[name], content, ctx.author]]

        await ctx.reply('Tag created.')

    @tag.command()
    @commands.guild_only()
    async def alias(self, ctx, old_name: commands.clean_content, new_name: commands.clean_content):
        """Creates a server-wide alias for a already existing tag."""

        if len(new_name) > 50:
            raise commands.BadArgument(f'{len(new_name)} character tag alias is too long (50 character max).')

        root = self.bot.get_command('tag')
        if new_name.split()[0] in root.all_commands:
            raise commands.BadArgument('This tag alias starts with a reserved word.')

        check = self._tags[ctx.guild.id]
        if not check:
            return await ctx.reply("Tag not found.")

        match = fuzzy.find(old_name, check)
        if not match[0]:
            total = 0
            for idx in range(len(match[1])):
                total += len(match[1][idx])
                if total > 1900:
                    match = match[1][:idx]

            if len(match[1]):
                return await ctx.reply('Tag not found. Did you mean...\n'+'\n'.join(tag for tag in match[1]))
            return await ctx.reply('Tag not found.')

        idx = check[match[2]].index(match[1])
        locale = self._tags[ctx.guild.id][match[2]][idx][0]

        if new_name not in locale:
            self._tags[ctx.guild.id][match[2]][idx][0].append(new_name)

        await ctx.reply(f'Alias "{new_name}" created for "{old_name}" tag.')


def setup(bot):
    bot.add_cog(Tags(bot))
