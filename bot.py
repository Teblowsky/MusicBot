import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config_db import get_db_connection
import logging
from subscription import SubscriptionManager

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

FREE_DAILY_LIMIT = 3600
MAX_QUEUE_FREE = 5
MAX_QUEUE_PREMIUM = 50
MAX_PLAYLIST_ITEMS = 20

# 🔓 Lista właścicieli z wiecznym premium
BOT_OWNERS = [488756862976524291]

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

ffmpeg_options = {
    'options': '-vn',
}

queues = {}
now_playing = {}
user_play_time = {}

# Konfiguracja yt-dlp
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'cookiesfrombrowser': ('chrome',),  # Użyj ciasteczek z Chrome
    'cookiefile': 'cookies.txt',  # Alternatywnie, użyj pliku z ciasteczkami
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'no_warnings': True,
    'quiet': True,
    'extract_flat': True,
    'force_generic_extractor': False
}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

def is_premium(user_id):
    if user_id in BOT_OWNERS:
        return True  # 🔐 Właściciel zawsze premium

    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT expires_at FROM subscriptions WHERE user_id = %s", (str(user_id),))
        result = cursor.fetchone()
        if result:
            expires_at = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return expires_at > datetime.now()
        return False
    finally:
        conn.close()

def get_user_daily_play_time(user_id):
    if user_id not in user_play_time:
        user_play_time[user_id] = {"total": 0, "last_reset": datetime.now()}
    if datetime.now().date() > user_play_time[user_id]["last_reset"].date():
        user_play_time[user_id] = {"total": 0, "last_reset": datetime.now()}
    return user_play_time[user_id]["total"]

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, requester_id=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.requester_id = requester_id
        self.start_time = None

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, requester_id=None):
        loop = loop or asyncio.get_event_loop()

        ytdl_format_options = {
            'format': 'bestaudio/best',
            'noplaylist': False,
            'quiet': True,
            'extract_flat': 'in_playlist',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192' if is_premium(requester_id) else '128',
            }]
        }

        ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
        players = []

        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

            if 'entries' in data:
                playlist_title = data.get('title', 'Playlista')
                await loop.run_in_executor(None, lambda: print(f"📋 Ładowanie playlisty: {playlist_title}"))
                
                for i, entry in enumerate(data['entries']):
                    if i >= MAX_PLAYLIST_ITEMS:
                        break
                    try:
                        if not entry or 'url' not in entry:
                            continue
                        entry_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(entry['url'], download=not stream))
                        if not entry_data:
                            continue
                        source = discord.FFmpegPCMAudio(source=entry_data['url'], **ffmpeg_options)
                        players.append(cls(source, data=entry_data, requester_id=requester_id))
                    except Exception as e:
                        print(f"⚠️ Pominięto niedostępny utwór: {e}")
                        continue
            else:
                source = discord.FFmpegPCMAudio(source=data['url'], **ffmpeg_options)
                players.append(cls(source, data=data, requester_id=requester_id))

            return players
        except Exception as e:
            print(f"Error downloading from URL: {e}")
            return None

@bot.command(name="play", help="Dodaje utwór lub playlistę do kolejki i odtwarza.")
async def play(ctx, *, url):
    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym.")
        return

    if not is_premium(ctx.author.id):
        daily_time = get_user_daily_play_time(ctx.author.id)
        if daily_time >= FREE_DAILY_LIMIT:
            await ctx.send("⛔ Przekroczyłeś limit 1h dziennie.\nUaktualnij do premium ✨")
            return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()

    async with ctx.typing():
        players = await YTDLSource.from_url(url, loop=bot.loop, stream=True, requester_id=ctx.author.id)
        if not players:
            await ctx.send("⚠️ Nie udało się załadować utworu. Sprawdź link.")
            return

        queue = get_queue(ctx.guild.id)
        max_queue = MAX_QUEUE_PREMIUM if is_premium(ctx.author.id) else MAX_QUEUE_FREE

        if len(queue) + len(players) > max_queue:
            await ctx.send(f"⛔ Limit kolejki osiągnięty ({max_queue} utworów).")
            return

        for player in players:
            queue.append({"player": player, "title": player.title, "requester_id": ctx.author.id})

        await ctx.send(f"✅ Dodano {len(players)} utwór(ów) do kolejki.")

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

async def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if queue:
        track = queue.pop(0)
        now_playing[ctx.guild.id] = track["title"]
        track["player"].start_time = datetime.now()
        ctx.voice_client.play(track["player"], after=lambda e: bot.loop.create_task(handle_song_end(ctx, track)))
        quality = "192kbps" if is_premium(track["requester_id"]) else "128kbps"
        await ctx.send(f"▶️ Teraz odtwarzane: {track['title']} ({quality})")
    else:
        now_playing[ctx.guild.id] = None

async def handle_song_end(ctx, track):
    if not is_premium(track["requester_id"]):
        elapsed_time = (datetime.now() - track["player"].start_time).total_seconds()
        user_play_time[track["requester_id"]]["total"] += elapsed_time
    await play_next(ctx)

@bot.command(name="skip", help="⏭️ Pomija aktualnie odtwarzany utwór.")
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("❌ Bot nie jest połączony z kanałem.")
        return
    if not ctx.voice_client.is_playing():
        await ctx.send("⚠️ Nie ma utworu do pominięcia.")
        return
    ctx.voice_client.stop()
    await ctx.send("⏭️ Utwór pominięty.")

@bot.command(name="stop", help="🛑 Zatrzymuje muzykę i czyści kolejkę.")
async def stop(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("❌ Bot nie jest połączony.")
        return
    queues[ctx.guild.id] = []
    now_playing[ctx.guild.id] = None
    ctx.voice_client.stop()
    await ctx.voice_client.disconnect()
    await ctx.send("🛑 Muzyka zatrzymana, kolejka wyczyszczona, bot rozłączony.")

@bot.command(name="premium", help="📊 Pokaż status premium.")
async def premium(ctx):
    is_user_premium = is_premium(ctx.author.id)
    daily_time = get_user_daily_play_time(ctx.author.id)
    embed = discord.Embed(title="🌟 Status Premium", color=0x6200ea)
    embed.add_field(name="Status", value="Premium ✨" if is_user_premium else "Free", inline=False)

    if not is_user_premium:
        remaining_time = max(0, FREE_DAILY_LIMIT - daily_time)
        embed.add_field(name="Pozostały czas dzienny",
                        value=str(timedelta(seconds=int(remaining_time))),
                        inline=True)

    embed.add_field(name="Limit kolejki",
                    value=f"{MAX_QUEUE_PREMIUM if is_user_premium else MAX_QUEUE_FREE} utworów",
                    inline=True)

    embed.add_field(name="Jakość audio",
                    value="192kbps" if is_user_premium else "128kbps",
                    inline=True)

    if not is_user_premium:
        embed.add_field(name="Zdobądź Premium",
                        value="• Nielimitowany czas\n• Większa kolejka\n• Lepsza jakość",
                        inline=False)

    await ctx.send(embed=embed)

async def on_ready(self):
    self.logger.info(f'Zalogowano jako {self.user.name} (ID: {self.user.id})')
    self.logger.info('------')

bot.run(TOKEN)
