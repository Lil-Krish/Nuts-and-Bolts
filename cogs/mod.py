import datetime, aiohttp
from typing import Optional
from io import BytesIO
from PIL import Image
from collections import Counter, defaultdict, OrderedDict
from operator import attrgetter

from .utils import checks
from .utils.paginator import Embed

from discord.ext import commands
import discord

class ContentCooldown(commands.CooldownMapping):
    def _bucket_key(self, message):
        return (message.channel.id, message.content)


class SpamCheck:
    def __init__(self):
        self.short_check = ContentCooldown.from_cooldown(15, 18.0, commands.BucketType.member)
        self.long_check = commands.CooldownMapping.from_cooldown(30, 37.0, commands.BucketType.channel)
    
    def is_spamming(self, message):
        if message.guild is None:
            return
        
        current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()
        short_bucket = self.short_check.get_bucket(message)
        long_bucket = self.long_check.get_bucket(message)
        
        return (short_bucket.update_rate_limit(current) or long_bucket.update_rate_limit(current))


class Reason(commands.Converter):
    async def convert(self, ctx, argument: commands.clean_content):
        info = f'{ctx.author} (ID: {ctx.author.id}): "{argument}"'
        if len(info) > 512:
            max_reason = 512-(len(info)-len(argument))
            raise commands.BadArgument(f'{len(argument)} character reason is too long ({max_reason} character max).')
        return info


class Mod(commands.Cog):
    """Moderation related commands."""
    def __init__(self, bot):
        self.bot = bot
        self._deleted_messages = {}
        self._spam_check = defaultdict(SpamCheck)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        checker = self._spam_check[message.guild.id] if message.guild else self._spam_check[message.channel.id]
        if checker.is_spamming(message):
            self.bot.blocked['global'].add(message.author)
            await message.author.send('You have been banned from the relevant server and globally blocked from using this bot for one day due to spamming.')
            if message.guild:
                await message.guild.ban(message.author, reason='Spam autoban.')
    
    async def _modify_list(self, ctx, data, bucket: Optional[str] = 'members', max_length: Optional[int] = 5):
        data = list(OrderedDict.fromkeys(data))
        if len(data) > max_length:
            await ctx.reply(f'You can only execute this action on {max_length} {bucket} at a time.')
        return data[:max_length]
    
    async def _modify_access(self, ctx, action, *, entities, bucket: Optional[str] = 'members', max_length: Optional[int] = 10, reason: Optional[Reason] = None):
        attrs = {
            'block' : 'add',
            'unblock' : 'remove',
            'softban' : ['ban', 'unban'],
        }
        
        entities = await self._modify_list(ctx, entities, max_length)
        
        if reason is None:
            reason = f'{ctx.author} (ID: {ctx.author.id}): No reason provided.'
        
        errors = (discord.Forbidden, discord.NotFound, KeyError, discord.HTTPException, commands.BadArgument)
        successes = []
        dump = [[] for _ in range(6)]
        for entity in entities:
            try:
                is_int = (type(entity) == int)
                if  is_int or checks.can_use(ctx, ctx.author, entity):
                    used = entity
                    if is_int:
                        entity = (await ctx.guild.fetch_ban(discord.Object(id=entity))).user
                    try:
                        getattr(self.bot.blocked[ctx.guild.id], attrs.get(action, str()))(entity)
                    except AttributeError:
                        try:
                            await getattr(ctx.guild, action)(entity, reason=reason)
                        except (AttributeError, KeyError):
                            try:
                                funcs = attrgetter(*attrs[action])(ctx.guild)
                                [func(entity, reason=reason) for func in funcs]
                            except (AttributeError, KeyError):
                                await getattr(entity, action)(reason=reason)
                    successes.append(used)
            except errors as e:
                dump[errors.index(type(e))].append(entity)
            else:
                dump[5].append(entity)
        
        val = str()
        embed = Embed(title=f'{action.capitalize()} {bucket.capitalize()}', ctx=ctx)
        causes = ('I cannot access this entity.', 'This entity has not been banned.', 'This entity has not been blocked.', 'Unexpected error.', 'This entity does not exist.', 'You cannot edit this entity.')
        attrs = ('\N{CROSS MARK}', '\N{WHITE HEAVY CHECK MARK}')
        for entity in entities:
            if entity in successes:
                val += f'{entity}\n'
            else:
                for signal in dump:
                    if entity in signal:
                        embed.add_field(name=f'{attrs[0]} {entity}', value=causes[dump.index(signal)], inline=False)
                        break
        
        if val:
            embed.add_field(name=f'{attrs[-1]} Success', value=val)
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def block(self, ctx, mentions: commands.Greedy[discord.Member]):
        """Blocks members from using the bot in the server, up to 10 at once.
        
        To use this command, you must have the Ban Members permission.
        """
        await self._modify_access(ctx, 'block', entities=mentions);
    
    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def unblock(self, ctx, mentions: commands.Greedy[discord.Member]):
        """Unblocks members from using the bot in the server, up to 10 at once.
        Globally blocked members will continue to be blocked until their limit is up.

        To use this command, you must have the Ban Members permission.
        """
        await self._modify_access(ctx, 'unblock', entities=mentions);
    
    @commands.command()
    @commands.guild_only()
    @checks.can_kick()
    async def kick(self, ctx, mentions: commands.Greedy[discord.Member], *, reason: Optional[Reason]):
        """Kicks members from the server, up to 5 at once.
        
        To use this command, you must have the Kick Members permission.
        The bot must have the Kick Members permission for this command to run.
        """
        await self._modify_access(ctx, 'kick', entities=mentions, reason=reason)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def ban(self, ctx, mentions: commands.Greedy[discord.Member], *, reason: Optional[Reason]):
        """Bans members from the server, up to 5 at once.
        
        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """
        await self._modify_access(ctx, 'ban', entities=mentions, reason=reason)

    @commands.command(aliases=['soft'])
    @commands.guild_only()
    @checks.can_ban()
    async def softban(self, ctx, mentions: commands.Greedy[discord.Member], *, reason: Optional[Reason]):
        """Softbans members from the server, up to 5 at once.
        
        Softbanning entails the ban and the immediate unban of a member, effectively kicking them while also removing their messages.
        
        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """
        await self._modify_access(ctx, 'softban', entities=mentions, reason=reason)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def unban(self, ctx, ids: commands.Greedy[int], *, reason: Optional[Reason]):
        """Revokes the ban from members on the server, up to 5 at once.
        
        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """
        await self._modify_access(ctx, 'unban', entities=ids, reason=reason)
    
    async def _modify_roles(self, ctx, action, *, entities, affixes, max_length: Optional[int] = 5, reason: Optional[Reason] = None):
        entities = await self._modify_list(ctx, entities, max_length)
        affixes = await self._modify_list(ctx, affixes, 'roles', max_length)
        
        errors = (discord.Forbidden, discord.HTTPException, commands.BadArgument)
        working = {}
        dump = [[] for _ in range(4)]
        for entity in entities:
            for affix in affixes:
                try:
                    if checks.can_set(ctx, ctx.author, affix):
                        await getattr(entity, action)(affix, reason=reason)
                        try:
                            working[affix].append(entity)
                        except:
                            working[affix] = [entity]
                    else:
                        dump[3].append(affix)
                except errors as e:
                    dump[errors.index(type(e))].append(affix)
        
        embed = Embed(title=f'{action[:-6].capitalize()} Roles', ctx=ctx)
        causes = ('I cannot access this entity.', 'Unexpected error.', 'This entity does not exist.', 'You cannot edit this entity.')
        attrs = ('\N{CROSS MARK}', '\N{WHITE HEAVY CHECK MARK}')
        for affix in affixes:
            if affix in working.keys():
                val = str()
                for entity in entities:
                    if entity in working[affix]:
                        val += f'{entity}\n'
                embed.add_field(name=f'{attrs[-1]} {affix}', value=val, inline=False)
            else:
                for signal in dump:
                    if affix in signal:
                        embed.add_field(name=f'{attrs[0]} {affix}', value=causes[dump.index(signal)], inline=False)
                        break
        
        await ctx.send(embed=embed)
    
    @commands.command(aliases=['add'])
    @commands.guild_only()
    @checks.manage_roles()
    async def give(self, ctx, mentions: commands.Greedy[discord.Member], roles: commands.Greedy[discord.Role], *, reason: Optional[Reason]):
        """Adds roles to members, up to 5 each.
        
        To use this command, you must have the Manage Roles permission.
        The bot must have the Manage Roles permission for this command to run.
        """
        await self._modify_roles(ctx, 'add_roles', entities=mentions, affixes=roles)
    
    @commands.command(aliases=['remove'])
    @commands.guild_only()
    @checks.manage_roles()
    async def take(self, ctx, mentions: commands.Greedy[discord.Member], roles: commands.Greedy[discord.Role], *, reason: Optional[Reason]):
        """Takes roles from members, up to 5 each.
        
        To use this command, you must have the Manage Roles permission.
        The bot must have the Manage Roles permission for this command to run.
        """
        await self._modify_roles(ctx, 'remove_roles', entities=mentions, affixes=roles)

    @commands.command(aliases=['purge'])
    @commands.guild_only()
    @commands.cooldown(rate=1, per=10.0, type=commands.BucketType.channel)
    @checks.manage_messages()
    async def cleanup(self, ctx, mentions: commands.Greedy[discord.Member], limit: int = 100):
        """Cleans up messages in the channel.
        
        If members are mentioned, this commands searches the channel history for messages sent by these members.
        Otherwise, all messages within the limit are deleted.
        
        Please note that this is a very expensive operation, so it may take a while for messages to be cleaned up.
        As a result, channels can only be cleaned up once every 10 seconds.

        Members with the Manage Messages permission have a limit of 100 messages.
        Members with the Manage Server permission have a limit of 1000 messages.
        
        The bot must have the Manage Messages permission for this command to run.
        """
        def check(msg):
            return msg.author in mentions if mentions else True
            
        manage_guild = ctx.channel.permissions_for(ctx.author).manage_guild
        max_delete = 1000 if manage_guild else 100

        if limit > max_delete:
            await ctx.reply(f'You can only delete up to {max_delete} messages at once.')
        
        async with ctx.channel.typing():
            deleted = await ctx.channel.purge(limit=min(max(0, limit), max_delete), check=check, before=ctx.message)

            cache = list(Counter(m.author for m in deleted).items())

            total = last = 0
            for data in cache:
                total += len(str(data[0]))+len(str(data[1]))+5
                if total > 1900:
                    idx = cache.index(data)
                    cache = cache[:idx]
                    break
            
            response = f'Deleted {sum(number for _, number in cache)} messages.\n' + '\n'.join('- '+str(member)+': '+str(number) for member, number in cache)
            try:
                await ctx.reply(response)
            except discord.HTTPException:
                await ctx.send(response)

    @commands.command(aliases=['whois'])
    @commands.guild_only()
    async def search(self, ctx, mention: discord.Member = None):
        """Searches info about a member in the server.
        
        Replying with this command will search the referred message author.
        """
        if mention is None:
            ref = ctx.message.reference
            if ref and isinstance(ref.resolved, discord.Message):
                mention = ref.resolved.author
            else:
                mention = ctx.author

        desc = 'User ID: '+str(mention.id)
        if ctx.guild and mention.nick:
            desc += '\n'+'Nickname: '+mention.nick
        
        attrs = {
            'online': 'https://i.postimg.cc/Ghvwxrsk/online.png',
            'idle': 'https://i.postimg.cc/gJ1Q3BzS/idle.png',
            'dnd': 'https://i.postimg.cc/3wPT9CgW/dnd.png',
            'offline': 'https://i.postimg.cc/1Xx78nBb/offline.png',
        }

        small, large = 40, 125
        
        async with aiohttp.ClientSession() as session:
            async with session.get(attrs[str(mention.status)]) as response:
                buffer = BytesIO(await response.read())
                status = Image.open(buffer).resize((small, small)).convert('RGBA')
        
        asset = mention.avatar_url_as(size=128)
        data = BytesIO(await asset.read())
        profile = Image.open(data).convert('RGBA')

        profile = profile.resize((large, large))
        profile.paste(status, (large-small, large-small), mask=status)

        embed = Embed(title=str(mention), description=desc, author=mention, ctx=ctx)

        with BytesIO() as binary:
            profile.save(binary, 'PNG')
            binary.seek(0)
            avatar = discord.File(fp=binary, filename='pfp.png')
        
        embed.set_thumbnail(url='attachment://pfp.png')
        embed.add_field(name='Creation Date', value=mention.created_at.strftime('%b %d, %Y'))
        embed.add_field(name='Join Date', value=mention.joined_at.strftime('%b %d, %Y'))
        embed.add_field(name='Top Roles', value='\n'.join(role.mention for role in mention.roles[1:6]))

        await ctx.send(file=avatar, embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        self._deleted_messages[message.channel.id] = message
        
    @commands.Cog.listener()
    async def on_message_edit(self, before, _):
        self._deleted_messages[before.channel.id] = before

    @commands.command()
    @commands.guild_only()
    async def snipe(self, ctx, channel: discord.TextChannel = None):
        """Retrieves the most recent edited/deleted message in a channel."""
        if channel is None:
            channel = ctx.channel

        try:
            message = self._deleted_messages[channel.id]
        except KeyError:
            return await ctx.reply("There's nothing to snipe!")

        embed = Embed(title=f'By {message.author}', ctx=ctx)
        embed.set_thumbnail(url='https://i.postimg.cc/mg0bg2wz/snipe.png')

        if message.content:
            embed.add_field(name='Content', value=f'{message.content}')
        if message.attachments:
            embed.add_field(name='Top Attachments', value='\n'.join(f'[{attachment.filename}]({attachment.url})' for attachment in message.attachments[:5]), inline=False)

        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.guild_only()
    @checks.is_mod()
    async def clone(self, ctx, channels: commands.Greedy[discord.TextChannel], *, reason: Optional[Reason]):
        """Clones text channels in the server, including permissions, up to 5 at once.

        To use this command, you must have the Manage Server permission.
        The bot must have the Manage Server permission for this command to run.
        """
        if not channels:
            channels = [ctx.channel]
        await self._modify_access(ctx, 'clone', entities=channels, bucket='channels', max_length=5, reason=reason)


def setup(bot):
    bot.add_cog(Mod(bot))
