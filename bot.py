# bot.py
import os
import discord
import mlbstatsapi
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default() # Set parameters for discord bot
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents) # Setup bot to read commands

mlb = mlbstatsapi.Mlb() # Initalize MLB API

players = [] # List of players

@bot.command() # Bot command to add player
async def add(ctx, *msg):
    player = ' '.join(msg)
    if player not in players:
        players.append(player)
        await ctx.send('Success: player found')
    else:
        await ctx.send('Error: player already in list')

@bot.command() # Bot command to remove player
async def remove(ctx, *msg):
    player = ' '.join(msg)
    if player in players:
        players.remove(player)
    else:
        await ctx.send('Error: Player not found.')

@bot.command() # Bot command to print player list
async def list(ctx, *args):
    await ctx.send(', '.join(players))

bot.run(TOKEN)