from discord.ext import commands
import discord

async def _check_permissions(ctx, perms, *, check=all):
    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())

async def _check_guild_permissions(ctx, perms, *, check=all):
    if ctx.guild is None:
        return False
    
    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())

async def can_use(ctx, user, target):
    if (user == ctx.guild.owner or (target != ctx.guild.owner and user.top_role > target.top_role)):
        return True
    else:
        raise commands.BadArgument(f'You cannot execute this action on {target} due to role/server hierarchy.')

def can_ban():
    async def wrap(ctx):
        return await _check_guild_permissions(ctx, {'ban_members': True})
    return commands.check(wrap)

def can_kick():
    async def wrap(ctx):
        return await _check_guild_permissions(ctx, {'kick_members': True})
    return commands.check(wrap)

def is_mod():
    async def wrap(ctx):
        return await _check_guild_permissions(ctx, {'manage_guild': True})
    return commands.check(wrap)

def is_admin():
    async def wrap(ctx):
        return await _check_guild_permissions(ctx, {'administrator': True})
    return commands.check(wrap)

async def error_handler(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send(error)
    elif isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.Forbidden):
            await ctx.send('The bot does not have permission to execute this command.')
        elif isinstance(original, discord.NotFound):
            await ctx.send(f'This does not exist: {original.text}')
        elif isinstance(original, discord.HTTPException):
            print(error) # await ctx.send('An unexpected error occurred. Please try again later.')
        else:
            await ctx.send(error.original)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send('You do not have permission to execute this command.')
    else:
        await ctx.send(error)
