import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config_db import get_db_connection

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FFMPEG_PATH = os.getenv("FFMPEG_PATH")

# Limity dla użytkowników
FREE_DAILY_LIMIT = 3600  # 1 godzina w sekundach
MAX_QUEUE_FREE = 5  # Maksymalna długość kolejki dla darmowych użytkowników
MAX_QUEUE_PREMIUM = 50  # Maksymalna długość kolejki dla premium

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',  # Premium users get 192kbps, free users get 128kbps
    }],
    'quiet': True,
    'extractaudio': True,
    'noplaylist': False,
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

queues = {}
now_playing = {}
user_play_time = {}  # Śledzi czas odtwarzania dla każdego użytkownika

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

def is_premium(user_id):
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
        if conn:
            conn.close()

def get_user_daily_play_time(user_id):
    if user_id not in user_play_time:
        user_play_time[user_id] = {"total": 0, "last_reset": datetime.now()}
    
    # Reset daily limit at midnight
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
        try:
            # Ustaw jakość dźwięku w zależności od statusu premium
            if is_premium(requester_id):
                ytdl_format_options['postprocessors'][0]['preferredquality'] = '192'
            else:
                ytdl_format_options['postprocessors'][0]['preferredquality'] = '128'

            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if 'entries' in data:
                # Playlist
                return [cls(discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=entry['url'], **ffmpeg_options), 
                          data=entry, requester_id=requester_id)
                        for entry in data['entries']]
            
            # Single video
            return [cls(discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=data['url'], **ffmpeg_options), 
                       data=data, requester_id=requester_id)]
        except Exception as e:
            print(f"Error downloading from URL: {e}")
            return None

@bot.command(name="play", help="Adds a song or playlist to queue and plays it.")
async def play(ctx, *, url):
    if not ctx.author.voice:
        await ctx.send("You must be in a voice channel to use this command.")
        return

    # Sprawdź limit czasu dla darmowych użytkowników
    if not is_premium(ctx.author.id):
        daily_time = get_user_daily_play_time(ctx.author.id)
        if daily_time >= FREE_DAILY_LIMIT:
            remaining_time = timedelta(seconds=FREE_DAILY_LIMIT - daily_time)
            await ctx.send(f"You've reached your daily limit of 1 hour. Upgrade to premium for unlimited music! ✨\nTime remaining: {remaining_time}")
            return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()

    async with ctx.typing():
        players = await YTDLSource.from_url(url, loop=bot.loop, stream=True, requester_id=ctx.author.id)
        if not players:
            await ctx.send("Failed to load the track. Please check the URL and try again.")
            return

        queue = get_queue(ctx.guild.id)
        
        # Sprawdź limit kolejki
        max_queue = MAX_QUEUE_PREMIUM if is_premium(ctx.author.id) else MAX_QUEUE_FREE
        if len(queue) + len(players) > max_queue:
            await ctx.send(f"Queue limit reached ({max_queue} tracks). {'Upgrade to premium for a larger queue! ✨' if not is_premium(ctx.author.id) else ''}")
            return

        for player in players:
            queue.append({"player": player, "title": player.title, "requester_id": ctx.author.id})
        
        if len(players) > 1:
            await ctx.send(f"Added {len(players)} tracks to queue")
        else:
            await ctx.send(f"Added to queue: {players[0].title}")

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

async def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if queue:
        track = queue.pop(0)
        now_playing[ctx.guild.id] = track["title"]
        
        # Rozpocznij śledzenie czasu
        track["player"].start_time = datetime.now()
        
        ctx.voice_client.play(track["player"], after=lambda e: bot.loop.create_task(handle_song_end(ctx, track)))
        
        # Pokaż informacje o jakości dźwięku
        quality = "192kbps" if is_premium(track["requester_id"]) else "128kbps"
        await ctx.send(f"Now playing: {track['title']} ({quality})")
    else:
        now_playing[ctx.guild.id] = None

async def handle_song_end(ctx, track):
    if not is_premium(track["requester_id"]):
        # Aktualizuj czas odtwarzania dla darmowych użytkowników
        elapsed_time = (datetime.now() - track["player"].start_time).total_seconds()
        user_play_time[track["requester_id"]]["total"] += elapsed_time
    
    await play_next(ctx)

@bot.command(name="premium", help="Shows premium features and status")
async def premium(ctx):
    is_user_premium = is_premium(ctx.author.id)
    daily_time = get_user_daily_play_time(ctx.author.id)
    
    embed = discord.Embed(title="🌟 Premium Status", color=0x6200ea)
    embed.add_field(name="Status", value="Premium ✨" if is_user_premium else "Free", inline=False)
    
    if not is_user_premium:
        remaining_time = max(0, FREE_DAILY_LIMIT - daily_time)
        embed.add_field(name="Daily Time Remaining", 
                       value=str(timedelta(seconds=int(remaining_time))), 
                       inline=True)
    
    embed.add_field(name="Queue Limit", 
                   value=f"{MAX_QUEUE_PREMIUM if is_user_premium else MAX_QUEUE_FREE} tracks",
                   inline=True)
    
    embed.add_field(name="Audio Quality", 
                   value="192kbps" if is_user_premium else "128kbps",
                   inline=True)
    
    if not is_user_premium:
        embed.add_field(name="Get Premium", 
                       value="Upgrade to premium for:\n" + 
                             "• Unlimited listening time\n" +
                             "• Higher audio quality (192kbps)\n" +
                             "• Larger queue (50 tracks)\n" +
                             "• Priority support",
                       inline=False)
    
    await ctx.send(embed=embed)

# Pozostałe komendy pozostają bez zmian...

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="!play | !premium"))

if __name__ == "__main__":
    bot.run(TOKEN)