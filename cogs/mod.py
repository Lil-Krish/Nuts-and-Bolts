import datetime
from collections import defaultdict
from .utils import checks
from discord.ext import commands
import discord

class ContentCooldown(commands.CooldownMapping):
    def _bucket_key(self, message):
        return (message.channel.id, message.content)

class SpamCheck:
    def __init__(self):
        self.by_content = ContentCooldown.from_cooldown(15, 18.0, commands.BucketType.member)
        self.new_user = commands.CooldownMapping.from_cooldown(30, 35.0, commands.BucketType.channel)
    
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
        self._spam_check = defaultdict(SpamCheck)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id in (self.bot.user.id, self.bot.owner_id):
            return
        
        checker = self._spam_check[message.guild.id] if message.guild else self._spam_check[message.channel.id]
        if checker.is_spamming(message):
            await message.channel.send('Spam point reached. You would be banned in a later update.')
    
    @commands.command()
    @commands.guild_only()
    @checks.can_kick()
    async def kick(self, ctx, mentions: commands.Greedy[discord.Member], *, reason=None):
        """Kicks members from the server.

        The command author will be notified of members who could not be kicked.

        To use this command, you must have the Kick Members permission.
        The bot must have the Kick Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)

        failed = 0
        kicked = []
        errors = (discord.HTTPException, commands.BadArgument)
        for member in mentions:
            try:
                await checks.can_use(ctx, ctx.author, member)
                await ctx.guild.kick(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    kicked.append(member)
                elif (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.reply(f'Kicked {len(mentions) - failed}/{len(mentions)} members.')

        if kicked:
            update = 'These members could not be kicked due to unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in kicked) if kicked else None

            author = await ctx.author.create_dm()
            await author.send(update)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def ban(self, ctx, mentions: commands.Greedy[discord.Member], *, reason=None):
        """Bans members from the server.

        The command author will be notified of members who could not be banned.

        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)

        failed = 0
        banned = []
        errors = (discord.HTTPException, commands.BadArgument)
        for member in mentions:
            try:
                await checks.can_use(ctx, ctx.author, member)
                await ctx.guild.ban(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    banned.append(member)
                elif (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.reply(f'Banned {len(mentions) - failed}/{len(mentions)} members.')

        if banned:
            update = 'These members could not be banned due to unexpected reasons: \n'+ '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in banned) if banned else None

            author = await ctx.author.create_dm()
            await author.send(update)

    @commands.command(aliases = ['soft'])
    @commands.guild_only()
    @checks.can_ban()
    async def softban(self, ctx, mentions: commands.Greedy[discord.Member], *, reason=None):
        """Softbans members from the server.

        Softbanning entails the ban and the immediate unban of a member, effectively kicking them while also removing their messages.
        The command author will be notified of members who could not be softbanned.

        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        
        failed = 0
        softbanned = []
        errors = (discord.HTTPException, commands.BadArgument)
        for member in mentions:
            try:
                await checks.can_use(ctx, ctx.author, member)
                await ctx.guild.ban(member, reason=full)
                await ctx.guild.unban(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    softbanned.append(member)
                elif (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.reply(f'Softbanned {len(mentions) - failed}/{len(mentions)} members.')

        if softbanned:
            update = 'These members could not be softbanned for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in softbanned) if softbanned else None

            author = await ctx.author.create_dm()
            await author.send(update)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def unban(self, ctx, ids: commands.Greedy[int], *, reason=None):
        """Revokes the ban from members on the server.

        The command author will be notified of members who could not be unbanned.

        To use this command, you must have the Ban Members permission.
        The bot must have the Ban Members permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)
        
        failed = 0
        unbanned = []
        errors = (discord.HTTPException, commands.BadArgument)
        for member_id in ids:
            try:
                member = await Conversion.get_banned_member(ctx, member_id)
                await ctx.guild.unban(member, reason=full)
            except errors as error:
                if (type(error) == errors[0]):
                    unbanned.append(ctx.bot.get_user(member_id))
                elif (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.reply(f'Unbanned {len(ids) - failed}/{len(ids)} members.')

        if unbanned:
            update = 'These members could not be unbanned for unexpected reasons: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in unbanned) if unbanned else None

            author = await ctx.author.create_dm()
            await author.send(update)
    
    @commands.command()
    @commands.guild_only()
    @checks.manage_roles()
    async def give(self, ctx, roles: commands.Greedy[discord.Role], mentions: commands.Greedy[discord.Member], reason=None):
        """Adds roles to members. 
        
        Members already with a mentioned role will not be affected.

        To use this command, you must have the Manage Roles permission.
        The bot must have the Manage Roles permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)

        failed_roles = 0
        working_roles = []
        errors = (discord.HTTPException, commands.BadArgument)
        for role in roles:
            try:
                await checks.can_set(ctx, ctx.author, role)
                working_roles.append(role)
            except errors as error:
                if (type(error) == errors[1]):
                    await ctx.send(error)
                failed_roles += 1

        failed_members = 0
        for member in mentions:
            try:
                await member.add_roles(*working_roles, reason=full)
            except discord.HTTPException:
                failed_members += 1

        await ctx.reply(f'Added {len(roles) - failed_roles}/{len(roles)} roles to {len(mentions) - failed_members}/{len(mentions)} members.')

    @commands.command()
    @commands.guild_only()
    @checks.manage_roles()
    async def take(self, ctx, roles: commands.Greedy[discord.Role], mentions: commands.Greedy[discord.Member], reason=None):
        """Takes roles to members. 
        
        Members already without a mentioned role will not be affected.

        To use this command, you must have the Manage Roles permission.
        The bot must have the Manage Roles permission for this command to run.
        """

        full = await Conversion.add_info(ctx, reason)

        failed_roles = 0
        working_roles = []
        errors = (discord.HTTPException, commands.BadArgument)
        for role in roles:
            try:
                await checks.can_set(ctx, ctx.author, role)
                working_roles.append(role)
            except errors as error:
                if (type(error) == errors[1]):
                    await ctx.send(error)
                failed_roles += 1

        failed_members = 0
        for member in mentions:
            try:
                await member.remove_roles(*working_roles, reason=full)
            except discord.HTTPException:
                failed_members += 1

        await ctx.reply(f'Removed {len(roles) - failed_roles}/{len(roles)} roles from {len(mentions) - failed_members}/{len(mentions)} members.')


def setup(bot):
    bot.add_cog(Mod(bot))