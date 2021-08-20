import asyncio
from typing import Optional
from collections import defaultdict, deque
import youtube_dl

from .utils import checks
from .utils.paginator import Embed, Pages

from discord.ext import commands, menus
from discord.errors import ClientException
import discord

class MusicMenu(menus.Menu):
    def __init__(self, data):
        super().__init__(timeout=15.0, clear_reactions_after=True)
        self.formatted = data
        self.index = 0
    
    async def send_initial_message(self, ctx, _):
        embed = Embed(title='Switch Music', description=f'Playing {self.formatted[0][1]} by {self.formatted[0][0]}', ctx=ctx)
        for data in self.formatted[1:]:
            embed.add_field(name=data[0], value=data[1])
        return await ctx.send(embed=embed)
    
    @menus.button(u'1\u20E3')
    async def equal_one(self, _, *, value=1):
        self.index = value
        self.stop()
    
    @menus.button(u'2\u20E3')
    async def equal_two(self, _):
        await self.equal_one(_, value=2)
    
    @menus.button(u'3\u20E3')
    async def equal_three(self, _):
        await self.equal_one(_, value=3)
    
    @menus.button(u'\N{CROSS MARK}')
    async def keep_music(self, _):
        await self.equal_one(_, value=0)
    
    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.index


class QueuePageSource(menus.ListPageSource):
    def __init__(self, data, context):
        super().__init__(entries=data, per_page=6)
        self.formatted = data
        self.context = context
    
    async def format_page(self, menu, entries):
        embed = Embed(title='Music Queue', ctx=self.context)
        for data in self.formatted:
            embed.add_field(name=data[0], value=data[1])
        return embed


class Music(commands.Cog):
    """Utilities providing voice functionality."""
    def __init__(self, bot):
        self.bot = bot
        self._ydl_opts = {
            'format': 'bestaudio',
            'quiet': True,
            'ignoreerrors': False,
        }
        self._ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'
        }
        self._queue = defaultdict(deque)
        self._bound = {}
    
    async def _connect(self, ctx):
        try:
            await ctx.author.voice.channel.connect()
            self._bound[ctx.guild.id] = ctx.channel
        except ClientException:
            return await ctx.reply('I am already connected to a VC. Please try again later.')
        except AttributeError:
            return await ctx.reply('Please try again after joining a VC.')
    
    async def _disconnect(self, ctx):
        await ctx.voice_client.disconnect()
        del self._bound[ctx.guild.id]
    
    def _get_extract(self, video):
        with youtube_dl.YoutubeDL(self._ydl_opts) as ydl:
            info = ydl.extract_info(video['link'], download=False)
            return info['formats'][0]['url']
    
    def _check_queue(self, ctx):
        try:
            self._queue[ctx.guild.id].popleft()
            if self._queue[ctx.guild.id]:
                ctx.voice_client.play(discord.FFmpegOpusAudio(self._get_extract(self._queue[ctx.guild.id][0]), **self._ffmpeg_opts), after=lambda _: self._check_queue(ctx))
        except (IndexError, ClientException):
            return
    
    def _play(self, ctx, video):
        ctx.voice_client.play(discord.FFmpegOpusAudio(self._get_extract(video), **self._ffmpeg_opts), after=lambda _: self._check_queue(ctx))
    
    @commands.command()
    @commands.guild_only()
    async def join(self, ctx):
        """Adds the bot to a VC with a text channel bound."""
        if not await self._connect(ctx):
            if self._queue[ctx.guild.id]:
                self._play(ctx, self._queue[0])
            await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    async def _check_conditions(self, ctx):
        if self._bound.get(ctx.guild.id) and ctx.channel != self._bound[ctx.guild.id]:
            return await ctx.reply(f'I am currently bound to {self._bound[ctx.guild.id].mention}.')
        try:
            if ctx.author in ctx.voice_client.channel.members:
                return True
            else:
                await ctx.reply('You are not in the VC that I am connected to.')
        except AttributeError as e:
            await ctx.reply('I am not currently connected to a VC.')
        return False
    
    @commands.command()
    @commands.guild_only()
    async def leave(self, ctx):
        """Removes the bot from a VC."""
        if await self._check_conditions(ctx):
            await self._disconnect(ctx)
        await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    @commands.command()
    @commands.guild_only()
    async def play(self, ctx, *, query: Optional[str]):
        """Plays music through YouTube search.
        
        Replying with this command will query the referred message content.
        """
        if not self._bound.get(ctx.guild.id):
            await self._connect(ctx)
        
        if await self._check_conditions(ctx):
            if not query:
                if self._queue[ctx.guild.id]:
                    if ctx.voice_client.is_playing():
                        return await ctx.reply('Already playing music.')
                    return self._play(ctx, self._queue[ctx.guild.id][0])
                else:
                    if query is None:
                        ref = ctx.message.reference
                        if ref and ref.resolved.content and isinstance(ref.resolved, discord.Message):
                            query = ref.resolved.content
                        else:
                            return await ctx.reply('Please provide a search query.')
            
            api = self.bot.get_cog('API')
            videos = await api.retrieve_videos(query, amount=4)
            add_queue = ctx.voice_client.is_playing()
            if not add_queue:
                self._queue[ctx.guild.id].appendleft(videos[0])
                self._play(ctx, videos[0])
            else:
                await ctx.reply('Music is already playing.')
            
            formatted = api.format_videos(videos)
            change = await MusicMenu(formatted).prompt(ctx)
            if not add_queue:
                if change:
                    try:
                        ctx.voice_client.stop()
                    finally:
                        self._queue[ctx.guild.id].appendleft(videos[change])
                        self._play(ctx, videos[change])
            else:
                self._queue[ctx.guild.id].append(videos[change])
                await ctx.reply('Added to queue.')
    
    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def queue(self, ctx):
        """Shows the server-wide music queue."""
        if not self._queue[ctx.guild.id]:
            return await ctx.reply('No existing queue.')
        
        api = self.bot.get_cog('API')
        formatted = api.format_videos(self._queue[ctx.guild.id])
        
        menu = Pages(QueuePageSource(formatted, ctx), ctx)
        await menu.start(ctx)
    
    @queue.command(aliases=['remove'])
    async def delete(self, ctx, index):
        """Deletes an item from the queue."""
        if index > len(self._queue[ctx.guild.id]) or index < 0:
            return await ctx.reply(f"The server music queue does not contain index {index}")
        
        if await self._check_conditions(ctx):
            del self._queue[ctx.guild.id][index-1]
            await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
    
    @commands.command(aliases=['voteskip'])
    @commands.guild_only()
    async def skip(self, ctx):
        """Skips the song playing if at least 75% of VC members agree."""
        if await self._check_conditions(ctx):
            if not len(self._queue[ctx.guild.id]) > 1:
                return await ctx.reply('No more songs in queue.')
            
            ups = 0
            if len(ctx.voice_client.channel.members) > 2:
                await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
                await asyncio.sleep(15.0)
                
                for reaction in ctx.message.reactions:
                    ups += (reaction.emoji == '\N{THUMBS UP SIGN}')
                
            if len(ctx.voice_client.channel.members) == 2 or (ups-1)/(len(ctx.voice_client.channel.members)-1) > 3/4:
                if ctx.voice_client.is_playing():
                    ctx.voice_client.stop()
                self._queue[ctx.guild.id].popleft()
                self._play(ctx, self._queue[ctx.guild.id][0])
                await ctx.reply('Skipped song.')
            else:
                await ctx.reply('Could not skip.')
    
    @commands.command()
    @commands.guild_only()
    @checks.is_mod()
    async def forceskip(self, ctx):
        """Forcefully skips the song playing.
        
        To use this command, you must have the Manage Server permission.
        """
        if await self._check_conditions(ctx):
            if not len(self._queue[ctx.guild.id]) > 1:
                return await ctx.reply('No more songs in queue.')

            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            self._queue[ctx.guild.id].popleft()
            self._play(ctx, self._queue[ctx.guild.id][0])
            await ctx.reply('Skipped song.')   
    
    @commands.command()
    @commands.guild_only()
    async def pause(self, ctx):
        """Pauses any music playing in VC."""
        if await self._check_conditions(ctx):
            if ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
            else:
                await ctx.reply('Music is not playing.')
    
    @commands.command()
    @commands.guild_only()
    async def resume(self, ctx):
        """Resumes paused music in VC."""
        if await self._check_conditions(ctx):
            if ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
            else:
                await ctx.reply('Music is not paused.')
    
    @commands.command()
    @commands.guild_only()
    async def stop(self, ctx):
        """Stops any music playing in VC."""
        if await self._check_conditions(ctx):
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await ctx.message.add_reaction('\N{THUMBS UP SIGN}')
            else:
                await ctx.reply('Music is not playing.')


def setup(bot):
    bot.add_cog(Music(bot))
