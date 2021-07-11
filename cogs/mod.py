import datetime, aiohttp
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw, ImageOps
from collections import Counter, defaultdict, OrderedDict
from .utils import checks
from .utils.paginator import Embed, Pages
from discord.ext import commands
import discord

class ContentCooldown(commands.CooldownMapping):
    def _bucket_key(self, message):
        return (message.channel.id, message.content)

class SpamCheck:
    def __init__(self):
        self.by_content = ContentCooldown.from_cooldown(15, 18.0, commands.BucketType.member)
        self.new_user = commands.CooldownMapping.from_cooldown(30, 37.0, commands.BucketType.channel)
    
    def is_new(self, member):
        now = datetime.datetime.utcnow()
        one_week_ago, two_months_ago = now - datetime.timedelta(days=7), now - datetime.timedelta(days=60)
        return member.created_at > two_months_ago and member.joined_at > one_week_ago

    def is_spamming(self, message):
        if message.guild is None:
            return
        
        current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()

        if self.is_new(message.author):
            new_bucket = self.new_user.get_bucket(message)
            if bucket.update_rate_limit(current):
                return True

        content_bucket = self.by_content.get_bucket(message)
        if content_bucket.update_rate_limit(current):
            return True

        return False

class Conversion(commands.Converter):
    @classmethod
    async def get_banned_member(cls, ctx, member_id):
        try:
            return await ctx.guild.fetch_ban(ctx.bot.get_user(member_id))
        except discord.NotFound:
            raise commands.BadArgument(f'{ctx.bot.get_user(member_id)} has not been banned.')
        except AttributeError:
            raise commands.BadArgument(f'{member_id} is not a valid member ID.')
    
    @classmethod
    async def add_info(cls, ctx, reason):
        shown = reason if reason else 'No reason provided.'
        full = f'{ctx.author} (ID: {ctx.author.id}): {shown}'

        if len(full) > 512:
            max_reason = 512 - len(full) + len(reason)
            raise commands.BadArgument(f'{len(reason)} character reason is too long ({max_reason} character max).')
        return full

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
            self.bot.blocked['global'].append(message.author)
            await message.author.send('You have been blocked from using this bot for 24 hours.')
    
    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def block(self, ctx, mentions: commands.Greedy[discord.Member] = []):
        """Blocks members from using the bot in the server, up to 10 at once.

        The command author will be notified of members who could not be blocked unexpectedly.

        To use this command, you must have the Ban Members permission.
        """
        
        mentions = list(OrderedDict.fromkeys(mentions))
        if len(mentions) > 10:
            await ctx.send('You can only block up to 10 members at a time from using the bot.')

        failed = 0
        command_failures = []
        errors = (discord.HTTPException, commands.BadArgument)

        mentions = mentions[:10]
        for member in mentions:
            if member in self.bot.blocked['global']:
                continue
            try:
                self.bot.blocked[ctx.guild.id].add(member)
            except errors as error:
                if (type(error) == errors[0]):
                    command_failures.append(member)
                elif (type(error) == errors[1]):
                    await ctx.reply(error)
                failed += 1
            except KeyError:
                self.bot.blocked[ctx.guild.id] = {member}

        await ctx.reply(f'Blocked {len(mentions) - failed}/{len(mentions)} members from using the bot in this server.')

        if command_failures:
            update = 'These members could not be blocked for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in command_failures)
            await ctx.author.send(update)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def unblock(self, ctx, mentions: commands.Greedy[discord.Member] = []):
        """Unblocks members from using the bot in the server, up to 10 at once.

        The command author will be notified of members who could not be unblocked unexpectedly.

        To use this command, you must have the Ban Members permission.
        """

        mentions = list(OrderedDict.fromkeys(mentions))
        if len(mentions) > 10:
            await ctx.send('You can only unblock up to 10 members at a time from using the bot.')

        failed = 0
        command_failures = []
        errors = (discord.HTTPException, commands.BadArgument)

        mentions = mentions[:10]
        globally_banned = []
        for member in mentions:
            if member in self.bot.blocked['global']:
                globally_banned.append(member)
                failed += 1
                continue
            try:
                self.bot.blocked[ctx.guild.id].remove(member)
            except errors as error:
                if (type(error) == errors[0]):
                    command_failures.append(member)
                elif (type(error) == errors[1]):
                    await ctx.reply(error)
                failed += 1
            except KeyError:
                pass
        
        await ctx.reply(f'Unblocked {len(mentions) - failed}/{len(mentions)} members from using the bot in this server.')

        if globally_banned:
            update = 'These members have been permanently blocked for 24 hours for spamming: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in globally_banned)
            await ctx.author.send(update)

        if command_failures:
            update = 'These members could not be unblocked for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in command_failures)
            await ctx.author.send(update)
    
    @commands.command()
    @commands.guild_only()
    @checks.can_kick()
    async def kick(self, ctx, mentions: commands.Greedy[discord.Member] = [], *, reason=None):
        """Kicks members from the server, up to 10 at once.

        The command author will be notified of members who could not be kicked unexpectedly.

        To use this command, you must have the Kick Members permission.
        The bot must have the Kick Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        mentions = list(OrderedDict.fromkeys(mentions))

        if len(mentions) > 10:
            await ctx.reply('You can only kick up to 10 members at a time.')

        failed = 0
        command_failures = []
        errors = (discord.HTTPException, commands.BadArgument)
        
        mentions = mentions[:10]
        for member in mentions:
            try:
                await checks.can_use(ctx, ctx.author, member)
                await ctx.guild.kick(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    command_failures.append(member)
                elif (type(error) == errors[1]):
                    await ctx.reply(error)
                failed += 1

        await ctx.reply(f'Kicked {len(mentions) - failed}/{len(mentions)} members.')

        if command_failures:
            update = 'These members could not be kicked for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in command_failures)
            await ctx.author.send(update)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def ban(self, ctx, mentions: commands.Greedy[discord.Member] = [], *, reason=None):
        """Bans members from the server, up to 10 at once.

        The command author will be notified of members who could not be banned unexpectedly.

        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        mentions = list(OrderedDict.fromkeys(mentions))

        if len(mentions) > 10:
            await ctx.reply('You can only ban up to 10 members at a time.')

        failed = 0
        command_failures = []
        errors = (discord.HTTPException, commands.BadArgument)

        mentions = mentions[:10]
        for member in mentions:
            try:
                await checks.can_use(ctx, ctx.author, member)
                await ctx.guild.ban(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    command_failures.append(member)
                elif (type(error) == errors[1]):
                    await ctx.reply(error)
                failed += 1

        await ctx.reply(f'Banned {len(mentions) - failed}/{len(mentions)} members.')

        if command_failures:
            update = 'These members could not be banned for unexpected reasons: \n'+ '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in command_failures)
            await ctx.author.send(update)

    @commands.command(aliases=['soft'])
    @commands.guild_only()
    @checks.can_ban()
    async def softban(self, ctx, mentions: commands.Greedy[discord.Member] = [], *, reason=None):
        """Softbans members from the server, up to 10 at once.

        Softbanning entails the ban and the immediate unban of a member, effectively kicking them while also removing their messages.
        The command author will be notified of members who could not be softbanned unexpectedly.

        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        mentions = list(OrderedDict.fromkeys(mentions))

        if len(mentions) > 10:
            await ctx.reply('You can only softban up to 10 members at a time.')

        failed = 0
        command_failures = []
        errors = (discord.HTTPException, commands.BadArgument)

        mentions = mentions[:10]
        for member in mentions:
            try:
                await checks.can_use(ctx, ctx.author, member)
                await ctx.guild.ban(member, reason=full)
                await ctx.guild.unban(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    command_failures.append(member)
                elif (type(error) == errors[1]):
                    await ctx.reply(error)
                failed += 1

        await ctx.reply(f'Softbanned {len(mentions) - failed}/{len(mentions)} members.')

        if command_failures:
            update = 'These members could not be softbanned for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in command_failures)
            await ctx.author.send(update)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def unban(self, ctx, ids: commands.Greedy[int] = [], *, reason=None):
        """Revokes the ban from members on the server, up to 10 at once.

        The command author will be notified of members who could not be unbanned unexpectedly.

        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        ids = list(OrderedDict.fromkeys(ids))

        if len(ids) > 10:
            await ctx.reply('You can only unban up to 10 members at a time.')

        failed = 0
        command_failures = []
        errors = (discord.HTTPException, commands.BadArgument)

        ids = ids[:10]
        for member_id in ids:
            try:
                member = await Conversion.get_banned_member(ctx, member_id)
                await ctx.guild.unban(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    unbanned.append(ctx.bot.get_user(member_id))
                elif (type(error) == errors[1]):
                    await ctx.reply(error)
                failed += 1

        await ctx.reply(f'Unbanned {len(ids) - failed}/{len(ids)} members.')

        if command_failures:
            update = 'These members could not be unbanned for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in command_failures)
            await ctx.author.send(update)
    
    @commands.command(aliases=['add'])
    @commands.guild_only()
    @checks.manage_roles()
    async def give(self, ctx, roles: commands.Greedy[discord.Role] = [], mentions: commands.Greedy[discord.Member] = [], reason=None):
        """Adds roles to members, up to 10 each. 
        
        Members already with a mentioned role will not be affected.
        The command author will be notified of roles/members who were not affected unexpectedly.

        To use this command, you must have the Manage Roles permission.
        The bot must have the Manage Roles permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        roles, mentions = list(OrderedDict.fromkeys(roles)), list(OrderedDict.fromkeys(mentions))

        if len(roles) > 10 or len(mentions) > 10:
            await ctx.reply('You can only add up to 10 roles to up to 10 members at a time.')

        failed_roles = 0
        working_roles, role_failures = [], []
        errors = (discord.HTTPException, commands.BadArgument)

        roles = roles[:10]
        for role in roles:
            try:
                await checks.can_set(ctx, ctx.author, role)
                working_roles.append(role)
            except errors as error:
                if (type(error) == errors[0]):
                    role_failures.append(role)
                if (type(error) == errors[1]):
                    await ctx.reply(error)
                failed_roles += 1

        failed_members = 0
        member_failures = []

        mentions = mentions[:10]
        for member in mentions:
            try:
                await member.add_roles(*working_roles, reason=full)
            except discord.HTTPException:
                member_failures.append(member)
                failed_members += 1

        await ctx.reply(f'Added {len(roles) - failed_roles}/{len(roles)} roles to {len(mentions) - failed_members}/{len(mentions)} members.')

        role_update = 'These roles could not be added for unexpected reasons: \n' + '\n'.join(str(role)+' ||(ID: '+str(role.id)+')||' for role in role_failures) if role_failures else None
        member_update = 'Roles could not be added to these members for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in member_failures) if member_failures else None

        if role_update or member_update:
            update = str(role_update or '') + '\n' + str(member_update or '')
            await ctx.author.send(update)
    
    @commands.command(aliases=['remove'])
    @commands.guild_only()
    @checks.manage_roles()
    async def take(self, ctx, roles: commands.Greedy[discord.Role] = [], mentions: commands.Greedy[discord.Member] = [], reason=None):
        """Takes roles from members, up to 10 each. 
        
        Members already without a mentioned role will not be affected.
        The command author will be notified of roles/members who were not affected unexpectedly.

        To use this command, you must have the Manage Roles permission.
        The bot must have the Manage Roles permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        roles, mentions = list(OrderedDict.fromkeys(roles)), list(OrderedDict.fromkeys(mentions))

        if len(roles) > 10 or len(mentions) > 10:
            await ctx.reply('You can only remove up to 10 roles to up to 10 members at a time.')

        failed_roles = 0
        working_roles, role_failures = [], []
        errors = (discord.HTTPException, commands.BadArgument)

        roles = roles[:10]
        for role in roles:
            try:
                await checks.can_set(ctx, ctx.author, role)
                working_roles.append(role)
            except errors as error:
                if (type(error) == errors[0]):
                    role_failures.append(role)
                if (type(error) == errors[1]):
                    await ctx.reply(error)
                failed_roles += 1

        failed_members = 0
        member_failures = []

        mentions = mentions[:10]
        for member in mentions:
            try:
                await member.remove_roles(*working_roles, reason=full)
            except discord.HTTPException:
                member_failures.append(member)
                failed_members += 1

        await ctx.reply(f'Removed {len(roles) - failed_roles}/{len(roles)} roles from {len(mentions) - failed_members}/{len(mentions)} members.')

        role_update = 'These roles could not be removed for unexpected reasons: \n' + '\n'.join(str(role)+' ||(ID: '+str(role.id)+')||' for role in role_failures) if role_failures else None
        member_update = 'Roles could not be removed from these members for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in member_failures) if member_failures else None

        if role_update or member_update:
            update = str(role_update or '') + '\n' + str(member_update or '')
            await ctx.author.send(update)

    @commands.command(aliases=['clean'])
    @commands.guild_only()
    @commands.cooldown(rate=1, per=5.0, type=commands.BucketType.member)
    @checks.manage_messages()
    async def cleanup(self, ctx, mentions: commands.Greedy[discord.Member], limit: int = 100):
        """Cleans up messages in the channel.
        
        If members are mentioned, this commands searches the channel history for messages sent by these members.
        Otherwise, all messages within the limit are deleted.
        
        Please note that this is a very expensive operation, so it may take a while for messages to be cleaned up.
        As a result, you can only cleanup messages once every 5 seconds.

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

            cache = Counter(m.author for m in deleted)
            
            response = f'Deleted {sum(cache.values())} messages.\n' + '\n'.join('- '+str(member)+': '+str(number) for member, number in cache.items())
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
                status = Image.open(buffer).resize((small, small)).convert("RGBA")
        
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

    @commands.command()
    @commands.guild_only()
    async def snipe(self, ctx, channel: discord.TextChannel = None):
        """Retrieves the most recent deleted message in a channel."""

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
    @checks.is_admin()
    async def clone(self, ctx, channels: commands.Greedy[discord.TextChannel] = None, reason=None):
        """Clones text channels in the server, including permissions, up to 5 at once.
        
        The command author will be notified of channels that were not cloned unexpectedly.

        To use this command, you must have the Manage Server permission.
        The bot must have the Manage Server permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)

        if channels is None:
            channels = [ctx.channel]

        channels = list(OrderedDict.fromkeys(channels))

        if len(channels) > 5:
            await ctx.reply('You can only clone up to 5 channels at a time.')
        
        channels = channels[:5]

        failed = index = receiver = 0
        command_failures = []
        for channel in channels:
            try:
                await channel.delete(reason=full)
                new = await channel.clone(reason=full)
                if (index == 0):
                    receiver = new
                index += 1
            except errors as error:
                command_failures.append(channel)
                failed += 1
        
        await ctx.reply(f'Cloned {len(channels) - failed}/{len(channels)} channels.')

        if command_failures:
            update = 'These channels could not be cloned for unexpected reasons: \n' + '\n'.join(str(channel)+' ||(ID: '+str(channel.id)+')||' for channel in command_failures)
            await ctx.author.send(update)


def setup(bot):
    bot.add_cog(Mod(bot))
