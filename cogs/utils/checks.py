from discord.ext import commands
import discord

async def _check_permissions(ctx, perms, *, check=all):
    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())

async def can_use(ctx, user, target):
    if (user == ctx.guild.owner or (target != ctx.guild.owner and user.top_role > target.top_role)):
        return True
    else:
        raise commands.BadArgument(f'You cannot execute this action on {target} due to role/server hierarchy.')

async def can_set(ctx, user, role):
    if (user == ctx.guild.owner or user.top_role > role):
        return True
    else:
        raise commands.BadArgument(f'You cannot execute this action on {role} due to role/server hierarchy.')

def can_ban():
    async def wrap(ctx):
        return await _check_permissions(ctx, {'ban_members': True})
    return commands.check(wrap)

def can_kick():
    async def wrap(ctx):
        return await _check_permissions(ctx, {'kick_members': True})
    return commands.check(wrap)

def is_mod():
    async def wrap(ctx):
        return await _check_permissions(ctx, {'manage_guild': True})
    return commands.check(wrap)

def is_admin():
    async def wrap(ctx):
        return await _check_permissions(ctx, {'administrator': True})
    return commands.check(wrap)

def is_owner():
    def wrap(ctx):
        return ctx.guild is not None and ctx.guild.owner == ctx.author
    return commands.check(wrap)

def manage_messages():
    async def wrap(ctx):
        return await _check_permissions(ctx, {'manage_messages': True, 'read_message_history': True})
    return commands.check(wrap)
    
def manage_roles():
    async def wrap(ctx):
        return await _check_permissions(ctx, {'manage_roles': True})
    return commands.check(wrap)

async def error_handler(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(error)
    elif isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.Forbidden):
            await ctx.reply('The bot does not have permission to execute this command.')
        elif isinstance(original, discord.HTTPException):
            await ctx.reply('An unexpected error occurred. Please try again later.')
        else:
            await ctx.reply(error.original)
    elif isinstance(error, commands.CheckFailure):
        await ctx.reply('You do not have permission to execute this command.')
    else:
        await ctx.reply(f'{error.__class__.__name__}: {error}')
