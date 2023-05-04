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

@bot.command() # Bot command to add player
async def add(ctx, *msg):
    print(msg)

bot.run(TOKEN)