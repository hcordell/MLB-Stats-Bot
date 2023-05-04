# bot.py
import os
import discord
import mlbstatsapi
import statsapi
from dotenv import load_dotenv
from discord.ext import commands, tasks

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
        if mlb.get_people_id(player): # Check if name matches player in database
            players.append(player)
            await ctx.send('Success: player found')
        else:
            await ctx.send('Error: player not found')
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

@tasks.loop(seconds=15.0)
async def update():
    for player in players:
        player_id = mlb.get_people_id(player)[0]
        for game in mlb.get_scheduled_games_by_date('2023-05-04'):
            try:
                print(mlb.get_game_box_score(game.gamepk).teams.home.players[f'id{player_id}'].stats)
            except:
                try:
                    print(mlb.get_game_box_score(game.gamepk).teams.away.players[f'id{player_id}'].stats)
                except:
                    continue
                else:
                    break
            else:
                break

@bot.event
async def on_ready():
    update.start()

bot.run(TOKEN)