# bot.py
import os
import discord
import mlbstatsapi
from datetime import date
from dotenv import load_dotenv
from discord.ext import commands, tasks

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default() # Set parameters for discord bot
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents) # Setup bot to read commands

mlb = mlbstatsapi.Mlb() # Initalize MLB API

players = [] # List of players
player_attributes = {} # Dictionary of details about players

@bot.command() # Bot command to add player
async def add(ctx, *msg):
    if ctx.channel.id == 1103511198474960916:
        player = ' '.join(msg)
        if player not in players:
            if mlb.get_people_id(player): # Check if name matches player in database
                players.append(player)
                player_attributes[f'{player}'] = {
                    'Position': '',
                    'Player ID': mlb.get_people_id(player)[0],
                    'Old Summary': ''
                }
                if mlb.get_person(player_attributes[f'{player}']['Player ID']).primaryposition.name == 'Pitcher':
                    player_attributes[f'{player}']['Position'] = 'pitching'
                else:
                    player_attributes[f'{player}']['Position'] = 'batting'
                await ctx.send('Success: player found')
            else:
                await ctx.send('Error: player not found')
        else:
            await ctx.send('Error: player already in list')

@bot.command() # Bot command to remove player
async def remove(ctx, *msg):
    if ctx.channel.id == 1103511198474960916:
        player = ' '.join(msg)
        if player in players:
            players.remove(player)
            player_attributes.pop(player)
            await ctx.send('Success: player removed')
        else:
            await ctx.send('Error: Player not found')

@bot.command() # Bot command to print player list
async def list(ctx, *args):
    if ctx.channel.id == 1103511198474960916:
        await ctx.send(', '.join(players))

@tasks.loop(minutes=1)
async def update():
    channel = bot.get_channel(1103827849007333447)
    for player in players:
        player_id = player_attributes[f'{player}']['Player ID']
        position = player_attributes[f'{player}']['Position']
        for game in mlb.get_scheduled_games_by_date(date.today()):
            try:
                summary = (f'{player}: {mlb.get_game_box_score(game.gamepk).teams.home.players[f"id{player_id}"].stats[position]["summary"]}')
                if player_attributes[f'{player}']['Old Summary'] != summary:
                    await channel.send(summary)
                    player_attributes[f'{player}']['Old Summary'] = summary
            except:
                try:
                    summary = (f'{player}: {mlb.get_game_box_score(game.gamepk).teams.away.players[f"id{player_id}"].stats[position]["summary"]}')
                    if player_attributes[f'{player}']['Old Summary'] != summary:
                        await channel.send(summary)
                        player_attributes[f'{player}']['Old Summary'] = summary
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