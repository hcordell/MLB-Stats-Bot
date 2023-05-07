# bot.py
import os
import discord
import mlbstatsapi
import functools
import asyncio
import typing
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

def unblock(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

@unblock
def get_player(mlb, player_name):
    try:
        player = mlb.get_people_id(player_name)
    except:
        return None
    return player

@unblock
def get_position(mlb, player, player_attributes):
    player_position = mlb.get_person(player_attributes[f'{player}']['Player ID']).primaryposition.name
    return player_position

@unblock
def get_schedule(mlb):
    schedule = mlb.get_scheduled_games_by_date(date.today())
    return schedule

@unblock
def get_stats(mlb, gameID, playerID, position):
    try:
        summary = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats[position]["summary"]
    except:
        try:
            summary = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats[position]["summary"]
        except:
            return None
    if summary:
        return summary
    return None

@bot.command() # Bot command to add player
#@commands.has_any_role('Admins', 'Moderator')
async def add(ctx, *msgs):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        player = ' '.join(msgs) # Capitalize the player's name
        player = player.split()
        i = 0
        for name in player:
            player[i] = name.capitalize()
            i += 1
        player = ' '.join(player)

        if player not in players:
            player_name = await get_player(mlb, player)
            if player_name: # Check if name matches player in database
                players.append(player)
                player_attributes[f'{player}'] = {
                    'Position': '',
                    'Player ID': player_name[0],
                    'Old Summary': ''
                }
                player_position = await get_position(mlb, player, player_attributes)
                if player_position == 'Pitcher':
                    player_attributes[f'{player}']['Position'] = 'pitching'
                else:
                    player_attributes[f'{player}']['Position'] = 'batting'
                await ctx.send('Success: player found')
            else:
                await ctx.send('Error: player not found')
        else:
            await ctx.send('Error: player already in list')

@bot.command() # Bot command to remove player
#@commands.has_any_role('Admins', 'Moderator')
async def remove(ctx, *msg):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        player = ' '.join(msg)
        if player in players:
            players.remove(player)
            player_attributes.pop(player)
            await ctx.send('Success: player removed')
        else:
            await ctx.send('Error: Player not found')

@bot.command() # Bot command to print player list
#@commands.has_any_role('Admins', 'Moderator')
async def list(ctx, *args):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        if len(players) == 0:
            await ctx.send('List is empty')
        else:
            await ctx.send(', '.join(players))

@tasks.loop(seconds=150)
async def update(channel):
    global current_date
    global schedule
    if current_date != date.today():
        schedule = await get_schedule(mlb)
        current_date = date.today()
    for player in players:
        player_id = player_attributes[f'{player}']['Player ID']
        position = player_attributes[f'{player}']['Position']
        for game in schedule:
            player_stats = await get_stats(mlb, game.gamepk, player_id, position)
            if player_stats:
                summary = (f'{player}: {player_stats}')
                if player_attributes[f'{player}']['Old Summary'] != summary:
                    await channel.send(summary)
                    player_attributes[f'{player}']['Old Summary'] = summary
                break

@bot.event
async def on_ready():
    channel = bot.get_channel(1103827849007333447) # Channel to send updates in
    update.start(channel)

@bot.event
async def setup_hook():
    global current_date
    global schedule
    current_date = date.today()
    schedule = await(get_schedule(mlb))

bot.run(TOKEN)