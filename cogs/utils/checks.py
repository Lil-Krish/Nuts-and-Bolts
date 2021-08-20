from discord.ext import commands

async def _check_permissions(ctx, perms, *, check=all):
    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())

def can_use(ctx, user, target):
    return (user == ctx.guild.owner or (target != ctx.guild.owner and user.top_role > target.top_role))

def can_set(ctx, user, role):
    return (user == ctx.guild.owner or user.top_role > role)

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
