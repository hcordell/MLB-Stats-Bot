# bot.py
import os
import discord
import mlbstatsapi
import functools
import asyncio
import aiohttp
import typing
from datetime import date
from dotenv import load_dotenv
from string import capwords
from discord.ext import commands, tasks

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default() # Set parameters for discord bot
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents) # Setup bot to read commands

mlb = mlbstatsapi.Mlb() # Initalize MLB API

players = [] # List of players
player_prices = [] # List of players to price check
player_uuids = {} # List of player UUIDs
player_attributes = {} # Dictionary of details about players

class TheShowPrices:
    def __init__(self) -> None:
        self.session = aiohttp.ClientSession()

    async def fetch(self, url):
        async with self.session.get(url) as response:
            return await response.json()
    
    async def close(self):
        await self.session.close()

async def main(PriceTool):
    for x in range(1, 74):
        data = await PriceTool.fetch(f'https://mlb23.theshow.com/apis/listings.json?type=mlb_card&page={x}&series_id=1337')
        for y in range(25):
            try:
                player_uuids[f"{data['listings'][y]['listing_name']}".lower()] = f"{data['listings'][y]['item']['uuid']}"
            except:
                break
    await PriceTool.close()

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
def get_winpct(mlb, player, gameID):
    winpct = player_attributes[f'{player}']['Win PCT'] = mlb.get_game_box_score(gameID).teams.home.team.record.winningpercentage
    return winpct

@unblock
def get_status(mlb, player, playerID, gameID):
    if player_attributes[f'{player}']['Position'] == 'batting':
        try:
            status = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].gamestatus.iscurrentbatter
        except:
            try:
                status = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].gamestatus.iscurrentbatter
            except:
                status = None
    elif player_attributes[f'{player}']['Position'] == 'pitching':
        try:
            status = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].gamestatus.iscurrentpitcher
        except:
            try:
                status = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].gamestatus.iscurrentpitcher
            except:
                status = None
    return status

@unblock
def get_stats(mlb, gameID, player, playerID, position):
    try:
        summary = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats[position]["summary"]
    except:
        try:
            summary = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats[position]["summary"]
        except:
            return None
    if summary:
        player_attributes[f'{player}']['Game ID'] = gameID
        return summary
    return None

@bot.command() # Bot command to add player
@commands.has_role('Admins')
async def add(ctx, *name):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        player = capwords(' '.join(name))
        if player not in players:
            player_name = await get_player(mlb, player)
            if player_name: # Check if name matches player in database
                players.append(player)
                player_attributes[f'{player}'] = {
                    'Position': None,
                    'Price': None,
                    'Allow Alerts': True,
                    'Player ID': player_name[0],
                    'Old Summary': None,
                    'Game ID': None,
                    'Win PCT': None,
                    'In Progress': True
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
@commands.has_role('Admins')
async def remove(ctx, *msg):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        player = ' '.join(msg)
        if player in players:
            players.remove(player)
            player_attributes.pop(player)
            await ctx.send('Success: player removed')
        else:
            await ctx.send('Error: player not found')

@bot.command() # Bot command to print player list
@commands.has_role('Admins')
async def list(ctx, *args):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        if len(players) == 0:
            await ctx.send('Error: list is empty')
        else:
            await ctx.send(', '.join(players))

@bot.command() # Bot command to add buy alert
@commands.has_role('Admins')
async def addAlert(ctx, *name):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        try:
            price = int(name[-1])
            player_upper = capwords(' '.join(name[:-1]))
            player = player_upper.lower()
            if player not in player_prices:
                player_attributes[f'{player_upper}']['Price'] = price
                player_prices.append(player)
                await ctx.send('Success: alert added')
            else:
                await ctx.send('Error: player already in list')
        except:
            await ctx.send('Error: player not added or invalid syntax')

@bot.command() # Bot command to remove buy alert
@commands.has_role('Admins')
async def removeAlert(ctx, *name):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        player = (' '.join(name)).lower()
        if player in player_prices:
            player_prices.remove(player)
            player_attributes[f'{capwords(player)}']['Price'] = None
            await ctx.send('Success: alert removed')
        else:
            await ctx.send('Error: player not found')

@bot.command() # Bot command to list all buy alerts
@commands.has_role('Admins')
async def listAlerts(ctx):
    if ctx.channel.id == 1103511198474960916: # Channel to send commands in
        if len(player_prices) == 0:
            await ctx.send('Error: list is empty')
        else:
            alert_list = [f"{capwords(player)} [{player_attributes[capwords(player)]['Price']}]" for player in player_prices]
            await ctx.send(', '.join(alert_list))

@tasks.loop(seconds=150)
async def update(channel):
    global current_date
    global schedule
    date_changed = False
    if current_date != date.today():
        schedule = await get_schedule(mlb)
        current_date = date.today()
        date_changed = True
    for player in players:
        if date_changed:
            player_attributes[f'{player}']['Game ID'] = None
            player_attributes[f'{player}']['Win PCT'] = None
            player_attributes[f'{player}']['In Progress'] = True
        player_id = player_attributes[f'{player}']['Player ID']
        position = player_attributes[f'{player}']['Position']
        gameID = player_attributes[f'{player}']['Game ID']
        stored_win_percent = player_attributes[f'{player}']['Win PCT']
        if player_attributes[f'{player}']['In Progress'] == True:
            for game in schedule:
                if gameID:
                    player_stats = await get_stats(mlb, gameID, player, player_id, position)
                    actual_win_percent = await get_winpct(mlb, player, gameID)
                    status = await get_status(mlb, player, player_id, gameID)
                else:
                    player_stats = await get_stats(mlb, game.gamepk, player, player_id, position)
                    actual_win_percent = await get_winpct(mlb, player, game.gamepk)
                    status = await get_status(mlb, player, player_id, game.gamepk)
                if player_stats:
                    player_attributes[f'{player}']['In Progress'] = True
                    if status:
                        summary = f'{player}: {player_stats} (Currently {position.capitalize()})'
                    else:
                        summary = f'{player}: {player_stats} (Not {position.capitalize()})'
                    print(stored_win_percent, actual_win_percent)
                    if stored_win_percent == None:
                        stored_win_percent = actual_win_percent
                    if stored_win_percent != actual_win_percent and player_stats != '0-0':
                        summary = f'FINAL: {player} {player_stats}'
                        player_attributes[f'{player}']['In Progress'] = False
                        await channel.send(summary)
                        player_attributes[f'{player}']['Old Summary'] = summary
                    elif player_attributes[f'{player}']['Old Summary'] != summary:
                        await channel.send(summary)
                        player_attributes[f'{player}']['Old Summary'] = summary
                    break

@tasks.loop(seconds=60)
async def update_prices(channel):
    PriceTool = TheShowPrices()
    for player in player_prices:
        uuid = player_uuids[f'{player}']
        data = await PriceTool.fetch(f'https://mlb23.theshow.com/apis/listing.json?uuid={uuid}')
        current_price = data['best_buy_price']
        player_upper = capwords(player)
        desired_price = player_attributes[f'{player_upper}']['Price']
        if current_price <= desired_price:
            if player_attributes[f'{player_upper}']['Allow Alerts']:
                await channel.send(f'BUY ALERT: {player_upper} is under {desired_price} stubs!')
                player_attributes[f'{player_upper}']['Allow Alerts'] = False
        elif current_price > desired_price:
            player_attributes[f'{player_upper}']['Allow Alerts'] = True
    await PriceTool.close()


@bot.event
async def on_ready():
    channel = bot.get_channel(1103827849007333447) # Channel to send updates in
    price_alerts = bot.get_channel(1106596697112596510) # Channel to send price updates in
    update.start(channel)
    update_prices.start(price_alerts)

@bot.event
async def setup_hook():
    global current_date
    global schedule
    current_date = date.today()
    schedule = await get_schedule(mlb)
    PriceTool = TheShowPrices()
    await main(PriceTool)

bot.run(TOKEN)