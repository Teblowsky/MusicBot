import discord
from discord.ext import commands
import wavelink
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config_db import get_db_connection
import logging
from subscription import SubscriptionManager
import json
import random
import string

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "localhost")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", "2333"))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

FREE_DAILY_LIMIT = 3600
MAX_QUEUE_FREE = 5
MAX_QUEUE_PREMIUM = 50
MAX_PLAYLIST_ITEMS = 20

# 🔓 Lista właścicieli z wiecznym premium
BOT_OWNERS = [488756862976524291]

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Konfiguracja loggerów
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Dodatkowy logger dla bota
bot_logger = logging.getLogger('music_bot')
bot_logger.setLevel(logging.INFO)

# Wyciszenie niepotrzebnych logów
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

queues = {}
now_playing = {}
user_play_time = {}

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.queues = {}
        self.now_playing = {}

    async def connect_nodes(self):
        """Łączy się z serwerem Lavalink"""
        await self.wavelink.connect(
            nodes=[
                wavelink.Node(
                    uri=f'http://{LAVALINK_HOST}:{LAVALINK_PORT}',
                    password=LAVALINK_PASSWORD
                )
            ]
        )

    def get_queue(self, guild_id):
        """Pobiera kolejkę dla danego serwera"""
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    async def play_next(self, guild_id):
        """Odtwarza następny utwór z kolejki"""
        queue = self.get_queue(guild_id)
        if not queue:
            return

        track = queue.pop(0)
        player = self.wavelink.get_player(guild_id)
        
        if not player:
            return

        await player.play(track)
        self.now_playing[guild_id] = track

player = MusicPlayer(bot)

@bot.event
async def on_ready():
    """Event wywoływany gdy bot jest gotowy"""
    bot_logger.info(f"Bot zalogowany jako {bot.user.name} (ID: {bot.user.id})")
    bot_logger.info(f"Bot jest na {len(bot.guilds)} serwerach")
    bot_logger.info("------")
    for guild in bot.guilds:
        bot_logger.info(f"Serwer: {guild.name} (ID: {guild.id})")
        bot_logger.info("------")
    bot_logger.info("Bot jest gotowy do działania!")
    
    # Łączenie z Lavalink
    await player.connect_nodes()

@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.Track, reason):
    """Event wywoływany gdy utwór się kończy"""
    guild_id = player.guild.id
    await player.play_next(guild_id)

@bot.command(name="play", help="Dodaje utwór lub playlistę do kolejki i odtwarza.")
async def play(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym!")
        return

    voice_channel = ctx.author.voice.channel
    
    # Łączenie z kanałem głosowym
    if not ctx.voice_client:
        try:
            await voice_channel.connect(cls=wavelink.Player)
        except Exception as e:
            bot_logger.error(f"❌ Błąd podczas łączenia z kanałem głosowym: {str(e)}")
            await ctx.send("❌ Nie mogę połączyć się z kanałem głosowym!")
            return

    try:
        async with ctx.typing():
            # Wyszukiwanie utworu
            tracks = await wavelink.NodePool.get_node().get_tracks(query)
            
            if not tracks:
                await ctx.send("❌ Nie znaleziono utworu!")
                return

            if isinstance(tracks, wavelink.TrackPlaylist):
                # To jest playlista
                for track in tracks.tracks[:MAX_PLAYLIST_ITEMS]:
                    queue = player.get_queue(ctx.guild.id)
                    if len(queue) >= (MAX_QUEUE_PREMIUM if is_premium(ctx.author.id) else MAX_QUEUE_FREE):
                        await ctx.send(f"❌ Kolejka jest pełna! (max {MAX_QUEUE_PREMIUM if is_premium(ctx.author.id) else MAX_QUEUE_FREE} utworów)")
                        return
                    
                    queue.append(track)
                    await ctx.send(f"✅ Dodano do kolejki: **{track.title}**")
            else:
                # To jest pojedynczy utwór
                track = tracks[0]
                queue = player.get_queue(ctx.guild.id)
                
                if len(queue) >= (MAX_QUEUE_PREMIUM if is_premium(ctx.author.id) else MAX_QUEUE_FREE):
                    await ctx.send(f"❌ Kolejka jest pełna! (max {MAX_QUEUE_PREMIUM if is_premium(ctx.author.id) else MAX_QUEUE_FREE} utworów)")
                    return
                
                queue.append(track)
                await ctx.send(f"✅ Dodano do kolejki: **{track.title}**")

            # Odtwarzanie jeśli nic nie gra
            if not ctx.voice_client.is_playing():
                await player.play_next(ctx.guild.id)

    except Exception as e:
        bot_logger.error(f"❌ Błąd podczas odtwarzania: {str(e)}")
        await ctx.send(f"❌ Wystąpił błąd: {str(e)}")

@bot.command(name="skip", help="⏭️ Pomija aktualnie odtwarzany utwór.")
async def skip(ctx):
    if not ctx.voice_client:
        await ctx.send("❌ Bot nie jest połączony z kanałem głosowym!")
        return

    player = ctx.voice_client
    if not player.is_playing():
        await ctx.send("❌ Nic nie jest odtwarzane!")
        return

    await player.stop()
    await ctx.send("⏭️ Pominięto utwór!")

@bot.command(name="stop", help="🛑 Zatrzymuje muzykę i czyści kolejkę.")
async def stop(ctx):
    if not ctx.voice_client:
        await ctx.send("❌ Bot nie jest połączony z kanałem głosowym!")
        return

    player = ctx.voice_client
    if not player.is_playing():
        await ctx.send("❌ Nic nie jest odtwarzane!")
        return

    player.queues.clear()
    await player.stop()
    await ctx.send("🛑 Zatrzymano odtwarzanie i wyczyszczono kolejkę!")

@bot.command(name="queue", help="📋 Pokazuje aktualną kolejkę.")
async def queue(ctx):
    queue = player.get_queue(ctx.guild.id)
    if not queue:
        await ctx.send("📋 Kolejka jest pusta!")
        return

    embed = discord.Embed(title="📋 Kolejka odtwarzania", color=discord.Color.blue())
    
    for i, track in enumerate(queue, 1):
        embed.add_field(
            name=f"{i}. {track.title}",
            value=f"Źródło: {track.source} | Długość: {timedelta(seconds=track.length)}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name="now", help="🎵 Pokazuje aktualnie odtwarzany utwór.")
async def now(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Nic nie jest odtwarzane!")
        return

    track = player.now_playing.get(ctx.guild.id)
    if not track:
        await ctx.send("❌ Nie można pobrać informacji o utworze!")
        return

    embed = discord.Embed(title="🎵 Teraz odtwarzane", color=discord.Color.green())
    embed.add_field(name="Tytuł", value=track.title, inline=False)
    embed.add_field(name="Źródło", value=track.source, inline=True)
    embed.add_field(name="Długość", value=timedelta(seconds=track.length), inline=True)
    
    await ctx.send(embed=embed)

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

# Uruchomienie bota
bot.run(TOKEN)
