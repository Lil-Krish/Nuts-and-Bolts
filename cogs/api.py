import urllib.parse, urllib.request
from typing import Optional
from io import BytesIO
from PIL import Image
import googletrans
from youtubesearchpython import VideosSearch, ResultMode
from pytio import Tio, TioRequest

from .utils.paginator import Embed, Pages

from discord.ext import commands, menus
import discord

class YouTubePageSource(menus.ListPageSource):
    def __init__(self, videos, context):
        super().__init__(entries=videos, per_page=6)
        self.context = context
    
    async def format_page(self, menu, entries):
        embed = Embed(title='YouTube Search', ctx=self.context)
        embed.set_thumbnail(url='https://i.postimg.cc/9QXFxh8X/youtube.png')
        for video in entries:
            title, url = video['title'], video['link']
            length, views = video['accessibility']['duration'], video['viewCount']['text']
            channel = video['channel']['name']
            embed.add_field(name=channel, value=f'[{title}]({url} "{length}\n{views}")')
        
        max_pages = self.get_max_pages()
        if max_pages > 1:
            embed.set_footer(text=f'Page {menu.current_page + 1}/{max_pages}')
        return embed


class API(commands.Cog):
    """Commands that use outside APIs."""
    def __init__(self, bot):
        self.bot = bot
        self.loop = self.bot.loop
        self.trans = googletrans.Translator()

    @commands.command()
    async def translate(self, ctx, *, message: Optional[commands.clean_content]):
        """Translates a message to English with Google Translate.
        
        Replying with this command will translate the referred message content.
        """
        if message is None:
            ref = ctx.message.reference
            if ref and ref.resolved.content and isinstance(ref.resolved, discord.Message):
                message = ref.resolved.content
            else:
                return await ctx.reply('Please provide a message to translate.')
        
        result = await self.loop.run_in_executor(None, self.trans.translate, message)

        embed = Embed(title='Translator', ctx=ctx)
        embed.set_thumbnail(url='https://i.postimg.cc/mDqNXRkM/translate.png')

        src = googletrans.LANGUAGES.get(result.src, '(Auto-Detected)').title()
        dest = googletrans.LANGUAGES.get(result.dest, 'Unknown').title()
        embed.add_field(name=f'From {src}', value=result.origin, inline=False)
        embed.add_field(name=f'To {dest}', value=result.text, inline=False)

        await ctx.send(embed=embed)

    @commands.command(aliases=['yt'])
    async def youtube(self, ctx, *, query: Optional[str]):
        """Queries Youtube and retrieves the top videos.
        
        Replying with this command will query the referred message content.
        """
        if query is None:
            ref = ctx.message.reference
            if ref and ref.resolved.content and isinstance(ref.resolved, discord.Message):
                query = ref.resolved.content
            else:
                return await ctx.reply('Please provide a message to query.')

        videos = await self.loop.run_in_executor(None, VideosSearch, query, 12)
        result = videos.result(mode=ResultMode.dict)['result']

        menu = Pages(YouTubePageSource(result, ctx), ctx)
        await menu.start(ctx)

    def generate_file(self, tex):
        margin, overlay = 20, '\hspace*{-0.5cm}'
        url = 'https://latex.codecogs.com/gif.latex?{0}'
        template = '\\dpi{{{}}} \\bg_white {}'

        query = template.format(200, overlay+tex)
        read = url.format(urllib.parse.quote(query))
        raw = urllib.request.urlopen(read).read()
        old = Image.open(BytesIO(raw))

        size = (old.size[0] + margin, old.size[1] + margin)
        new = Image.new("RGB", size, (255, 255, 255))
        new.paste(old, (int(margin / 2), int(margin / 2)))

        data = BytesIO()
        new.save(data, 'PNG')

        data.seek(0)
        return data

    @commands.command(aliases=['tex'])
    async def latex(self, ctx, *, code: Optional[str]):
        """Compiles a LaTeX image with the CodeCogs equation editor.
        
        Replying with this command will parse the referred message content.
        """
        if code is None:
            ref = ctx.message.reference
            if ref and ref.resolved.content and isinstance(ref.resolved, discord.Message):
                code = ref.resolved.content
            else:
                return await ctx.reply('Please provide code to parse.')
        
        generated = await self.loop.run_in_executor(None, self.generate_file, code)
        await ctx.reply(file=discord.File(generated, filename='latex.png'))

    @commands.command()
    async def run(self, ctx, language, *, code: Optional[str]):
        """Runs code with the Try It Online interpreter.
        
        Languages currently supported: Python 3, C, C++, C#, Java, Javascript, Rust, and PHP.

        Replying with this command will parse the referred message content.
        """
        if code is None:
            ref = ctx.message.reference
            if ref and ref.resolved.content and isinstance(ref.resolved, discord.Message):
                code = ref.resolved.content
            else:
                return await ctx.reply('Please provide code to parse.')
        
        instance = Tio()

        attrs = {
            'python3' : (('py3', 'py', 'python3', 'python'), 'https://i.postimg.cc/s21LPtxY/python.png'),
            'c-gcc' : (('c'), 'https://i.postimg.cc/vZZ2MpWJ/c.png'),
            'cpp-gcc' : (('cpp', 'c++'), 'https://i.postimg.cc/YSVsdbLJ/cpp.png'),
            'cs-csc' : (('cs', 'csharp', 'c#'), 'https://i.postimg.cc/FFbMX1DV/csharp.png'),
            'java-jdk' : (('java'), 'https://i.postimg.cc/50Lnn1VC/java.png'),
            'javascript-node' : (('js', 'javascript'), 'https://i.postimg.cc/kgGzSs9T/javascript.png'),
            'rust' : (('rs', 'rust'), 'https://i.postimg.cc/vmYMVW4J/rust.png'),
            'php' : (('php'), 'https://i.postimg.cc/0jDd1n6z/php.png'),
        }

        access = idx = 0
        for key, value in attrs.items():
            if language in value[0]:
                access = key
                break
            idx += 1
        
        if idx == len(attrs):
            return await ctx.reply('This language is not currently supported.')
        
        request = TioRequest(lang=access, code=code)
        result = await self.loop.run_in_executor(None, instance.send, request)

        embed = Embed(title=attrs[access][0][-1].capitalize(), ctx=ctx)
        embed.set_thumbnail(url=attrs[access][1])

        names = ['Real Time', 'User Time', 'Sys. Time', 'CPU Share', 'Exit Code']

        read = str(result.debug.decode('utf-8'))

        cut = read.index(names[0].capitalize())
        data = read[cut-1:].split('\n')

        times = []
        for idx in range(1, 5):
            times.append(''.join(data[idx][11:].split(' ')))
        
        times.append(data[5][11:])

        for idx in range(len(names)):
            embed.add_field(name=names[idx], value=times[idx])

        if result.error:
            if len(result.error) > 1024:
                return await ctx.reply('Error message is too long to be displayed.')
            embed.add_field(name='Error', value='```\n'+result.error[:cut-2]+'```')
        else:
            if len(result.result) > 1024:
                return await ctx.reply('Standard output is too long to be displayed.')
            embed.add_field(name='Standard Output', value='```\n'+result.result+'```')
        
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(API(bot))
