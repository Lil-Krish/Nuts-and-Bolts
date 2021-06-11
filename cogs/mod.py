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
    async def get_banned_member(cls, ctx, member):
        if member.isdecimal():
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=int(member)))
            except discord.NotFound:
                raise commands.BadArgument('This member has not been banned.')
        
        if '#' not in member:
            raise commands.BadArgument(f'{member} is not a valid member ID or user#discriminator pair.')
        
        ban_list = await ctx.guild.bans()
        entity = discord.utils.find(lambda u: str(u.user) == member, ban_list)

        if entity is None:
            raise commands.BadArgument('This member has not been banned.')
        return entity

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

    async def cog_command_error(self, ctx, error):
        await checks.error_handler(ctx, error)

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
                kicked.append(member)
            except (discord.HTTPException, commands.BadArgument) as error:
                if (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.send(f'Kicked {len(mentions) - failed}/{len(mentions)} members.')

        update = 'Successfully kicked: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in kicked) if kicked else None

        author = await ctx.author.create_dm()
        await author.send(update)

    @commands.command()
    @commands.guild_only()
    @checks.can_ban()
    async def ban(self, ctx, mentions: commands.Greedy[discord.Member], *, reason=None):
        """Bans members from the server.

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
                banned.append(member)
            except (discord.HTTPException, commands.BadArgument) as error:
                if (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.send(f'Banned {len(mentions) - failed}/{len(mentions)} members.')

        update = 'Successfully banned: \n'+ '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in banned) if banned else None

        author = await ctx.author.create_dm()
        await author.send(update)

    @commands.command(aliases = ['soft'])
    @commands.guild_only()
    @checks.can_ban()
    async def softban(self, ctx, mentions: commands.Greedy[discord.Member], *, reason=None):
        """Softbans members from the server.

        Softbanning entails the ban and the immediate unban of a member, effectively kicking them while also removing their messages.

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
                softbanned.append(member)
            except (discord.HTTPException, commands.BadArgument) as error:
                if (type(error) == errors[1]):
                    await ctx.send(error)
                failed += 1

        await ctx.send(f'Softbanned {len(mentions) - failed}/{len(mentions)} members.')

        update = 'Successfully softbanned: \n' + '\n'.join(str(member)+' ||(ID: '+str(member.id)+')||' for member in softbanned) if softbanned else None

        if update:
            author = await ctx.author.create_dm()
            await author.send(update)

def setup(bot):
    bot.add_cog(Mod(bot))