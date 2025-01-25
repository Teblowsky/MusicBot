@bot.command(name="premium_feature")
async def premium_feature(ctx):
    if not is_subscribed(ctx.author.id):
        await ctx.send("Ta funkcja jest dostępna tylko dla subskrybentów. Odwiedź https://twój-serwer.com, aby się zapisać.")
        return

    # Kod dla funkcji premium
    await ctx.send("Witaj, subskrybencie! Oto Twoja funkcja premium.")