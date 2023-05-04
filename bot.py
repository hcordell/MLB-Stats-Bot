# bot.py
import os
import discord
import mlbstatsapi
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

mlb = mlbstatsapi.Mlb()

@client.event
async def on_ready():
    print('Discord bot has connected!')

@client.event
async def on_message(message):
    print(f'From {message.author}: {message.content}')

client.run(TOKEN)
