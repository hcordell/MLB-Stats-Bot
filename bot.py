# bot.py
import os
import discord
import mlbstatsapi
import functools
import asyncio
import aiohttp
import typing
import certifi
from datetime import datetime, date
from dotenv import load_dotenv
from string import capwords
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PASSWORD = os.getenv('PASSWORD')

uri = f"mongodb+srv://Chimaezss:{PASSWORD}@mlbstatsbotdb.wcpwbzb.mongodb.net/?retryWrites=true&w=majority&tls=true"
client = AsyncIOMotorClient(uri, server_api=ServerApi('1'), tlsCAFile=certifi.where())

intents = discord.Intents.default() # Set parameters for discord bot
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents) # Setup bot to read commands

mlb = mlbstatsapi.Mlb() # Initalize MLB API

players = set() # List of players
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

async def loadData():
    player_collection = client.players.players
    docs = player_collection.find()
    player_list = await docs.to_list(length=None)
    for player in player_list:
        players.add(player['Name'])
        player_attributes[f'{player["Name"]}'] = player['Attributes']

async def main(PriceTool):
    for x in range(1, 74):
        data = await PriceTool.fetch(f'https://mlb24.theshow.com/apis/listings.json?type=mlb_card&page={x}&series_id=1337')
        for y in range(25):
            try:
                player_name = capwords(f"{data['listings'][y]['listing_name']}")
                player_uuids[f"{player_name}"] = f"{data['listings'][y]['item']['uuid']}"
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
def get_game_finish(mlb, gameID):
    status = mlb.get_game(gameID)['metadata']['gameevents']
    if 'game_finished' in status:
        return True
    return False

@unblock
def get_status(mlb, player, playerID, gameID):
    if player_attributes[f'{player}']['Team'] == 'Home':
        try:
            status = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].gamestatus.iscurrentpitcher
        except:
            status = None
            player_attributes[f'{player}']['Team'] = 'Unknown'
    elif player_attributes[f'{player}']['Team'] == 'Away':
        try:
            status = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].gamestatus.iscurrentpitcher
        except:
            status = None
            player_attributes[f'{player}']['Team'] = 'Unknown'
    else:
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
    if player_attributes[f'{player}']['Team'] == 'Home':
        game = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats[position]
        if game != None:
            player_attributes[f'{player}']['Game ID'] = gameID
        summary = game.stats[position]['summary']
    elif player_attributes[f'{player}']['Team'] == 'Away':
        game = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats[position]
        if game != None:
            player_attributes[f'{player}']['Game ID'] = gameID
        summary = game.stats[position]['summary']
    else:
        try:
            game = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats[position]
            if game != None:
                player_attributes[f'{player}']['Game ID'] = gameID
            summary = game.stats[position]['summary']
            player_attributes[f'{player}']['Team'] = 'Home'
        except:
            try:
                game = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats[position]
                if game != None:
                    player_attributes[f'{player}']['Game ID'] = gameID
                summary = game.stats[position]['summary']
                player_attributes[f'{player}']['Team'] = 'Away'
            except Exception as e:
                if str(e)[0] == 'i':
                    player_attributes[f'{player}']['Game ID'] = gameID
                    player_attributes[f'{player}']['Start Time'] = mlb.get_game(gameID)['gamedata']['datetime']['time']
                print(f'Error: wrong game or violation ({player})')
                print(f'{e}\n')
                player_attributes[f'{player}']['Team'] = 'Unknown'
                return None
    if summary:
        player_attributes[f'{player}']['Game ID'] = gameID
        status = mlb.get_game(gameID)['metadata']['gameevents']
        if 'game_finished' in status:
            finished = True
        else:
            finished = False
        if position == 'pitching' and finished:
            try:
                bsv = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats['pitching']['blownsaves']
                sv = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats['pitching']['saves']
            except:
                bsv = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats['pitching']['blownsaves']
                sv = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats['pitching']['saves']
            if bsv == 1:
                summary += ', 1 BSV'
            elif sv == 1:
                summary += ', 1 SV'
        return summary
    return None

@bot.command() # Bot command to create a buy alert for a player
@commands.has_role('Admins')
async def buy(ctx, *name):
    if ctx.channel.id == 1109551093081448508: # Channel to send commands in
        player = capwords(' '.join(name[:-1]))
        if name[-1].isnumeric == False:
            await ctx.send('Error: price not specified')
        elif player not in players:
            player_name = await get_player(mlb, player)
            if player_name: # Check if name matches player in database
                if update.is_running():
                    update.cancel()
                players.add(player)
                player_attributes[f'{player}'] = {
                    'Position': None,
                    'Type': 'Buy',
                    'Team': 'Unknown',
                    'Price': int(name[-1]),
                    'Allow Alerts': True,
                    'Player ID': player_name[0],
                    'Old Summary': None,
                    'Game ID': None,
                    'In Progress': True,
                    'Message': None
                }
                player_position = await get_position(mlb, player, player_attributes)
                if player_position == 'Pitcher':
                    player_attributes[f'{player}']['Position'] = 'pitching'
                else:
                    player_attributes[f'{player}']['Position'] = 'batting'
                await ctx.send('Success: player found')
                channel = bot.get_channel(996715384365396038)
                update.start(channel)
            else:
                await ctx.send('Error: player not found')
        else:
            await ctx.send('Error: player already in list')

@bot.command() # Bot command to create a sell alert for a player
@commands.has_role('Admins')
async def sell(ctx, *msg):
    if ctx.channel.id == 1109551093081448508:
        if msg[-1].isnumeric() == False:
            await ctx.send('Error: no price specified')
        else:
            player = capwords(' '.join(msg[:-1]))
            sell_price = int(msg[-1])
            player_attributes[f'{player}']['Type'] = 'Sell'
            player_attributes[f'{player}']['Price'] = sell_price
            player_attributes[f'{player}']['Allow Alerts'] = True
            await ctx.send('Success: sell alert created')

@bot.command() # Bot command to remove player
@commands.has_role('Admins')
async def remove(ctx, *msg):
    if ctx.channel.id == 1109551093081448508: # Channel to send commands in
        player = capwords(' '.join(msg))
        if player in players:
            players.remove(player)
            player_attributes.pop(player)
            await client.players.players.delete_one({'Name': f'{player}'})
            await ctx.send('Success: player removed')
        else:
            await ctx.send('Error: player not found')

@bot.command() # Bot command to print player list
async def list(ctx, *args):
    if ctx.channel.id == 1109551093081448508: # Channel to send commands in
        if len(players) == 0:
            await ctx.send('Error: list is empty')
        else:
            alert_list = [f"[{player_attributes[f'{player}']['Type']}] {player} [{player_attributes[player]['Price']}]" for player in players]
            await ctx.send(', '.join(alert_list))

@bot.command() # Bot command to message player prices
async def prices(ctx, *args):
    if isinstance(ctx.channel, discord.channel.DMChannel):
        user_id = ctx.author.id
        user = await bot.fetch_user(user_id)
        price_list = []
        for player in players:
            alert_type = player_attributes[f'{player}']['Type']
            price = player_attributes[f'{player}']['Price']
            price_list.append(f'[{alert_type}] {player}: {price}')
        await user.send('\n'.join(price_list))

@bot.command() # Bot command to shutdown and save
@commands.has_role('Admins')
async def shutdown(ctx, *args):
    player_db = client.players
    player_collection = player_db.players
    docs = []
    for player in players:
        doc = await player_collection.find_one({'Name': player})
        player_attributes[f'{player}']['Game ID'] = None
        player_attributes[f'{player}']['In Progress'] = True
        player_attributes[f'{player}']['Message'] = None
        player_attributes[f'{player}']['Team'] = None
        if doc:
            updates = {'$set': {'Attributes': player_attributes[f'{player}']}}
            player_collection.update_one({'Name': player}, updates)
        else:
            doc = {
                'Name': player,
                'Attributes': player_attributes[f'{player}']
            }
            docs.append(doc)
    if len(docs) != 0:
        await player_collection.insert_many(docs)
    await ctx.send('Shutting Down...')
    await bot.close()

@bot.command() # Bot command to restart
async def restart(ctx, *args):
    os.startfile('bot.py')
    await ctx.send('Now Restarting...')
    await ctx.invoke(bot.get_command('shutdown'))

@tasks.loop(minutes=1)
async def restart_loop(channel):
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    if current_time == '03:00':
        player_db = client.players
        player_collection = player_db.players
        docs = []
        for player in players:
            doc = await player_collection.find_one({'Name': player})
            player_attributes[f'{player}']['Game ID'] = None
            player_attributes[f'{player}']['In Progress'] = True
            player_attributes[f'{player}']['Message'] = None
            player_attributes[f'{player}']['Team'] = None
            if doc:
                updates = {'$set': {'Attributes': player_attributes[f'{player}']}}
                player_collection.update_one({'Name': player}, updates)
            else:
                doc = {
                    'Name': player,
                    'Attributes': player_attributes[f'{player}']
                }
                docs.append(doc)
        if len(docs) != 0:
            await player_collection.insert_many(docs)
        os.startfile('bot.py')
        await bot.close()

@tasks.loop(minutes=5)
async def update(channel):
    global current_date
    global schedule
    date_changed = False
    if current_date != date.today():
        schedule = await get_schedule(mlb)
        current_date = date.today()
        date_changed = True
        await asyncio.sleep(28800)
    for player in players:
        await asyncio.sleep(30)
        if date_changed:
            player_attributes[f'{player}']['Game ID'] = None
            player_attributes[f'{player}']['In Progress'] = True
            player_attributes[f'{player}']['Start Time'] = '0:00'
            player_attributes[f'{player}']['Message'] = None
            player_attributes[f'{player}']['Team'] = None
        player_id = player_attributes[f'{player}']['Player ID']
        position = player_attributes[f'{player}']['Position']
        gameID = player_attributes[f'{player}']['Game ID']
        message = player_attributes[f'{player}']['Message']
        invalidStats = False
        if player_attributes[f'{player}']['In Progress'] == True:
            cur_time = int(datetime.now().strftime('%H')) % 12
            for game in schedule:
                if player_attributes[f'{player}']['Start Time'][0] > cur_time:
                    break
                if gameID:
                    player_stats = await get_stats(mlb, gameID, player, player_id, position)
                    if player_attributes[f'{player}']['Position'] == 'pitching':
                        await asyncio.sleep(10)
                        status = await get_status(mlb, player, player_id, game.gamepk)
                    else:
                        status = None
                else:
                    player_stats = await get_stats(mlb, game.gamepk, player, player_id, position)
                    if player_attributes[f'{player}']['Position'] == 'pitching':
                        await asyncio.sleep(10)
                        status = await get_status(mlb, player, player_id, game.gamepk)
                    else:
                        status = None
                if player_stats:
                    player_attributes[f'{player}']['In Progress'] = True
                    if player_stats == '0-0' or player_stats == '0.0 IP, 0 ER, 0 K, 0 BB':
                        invalidStats = True
                    if status and position == 'pitching':
                        summary = f'{player}: {player_stats} (Currently {position.capitalize()})'
                    elif position == 'pitching':
                        summary = f'{player}: {player_stats} (Not {position.capitalize()})'
                    else:
                        summary = f'{player}: {player_stats}'
                    if gameID:
                        gameOver = await get_game_finish(mlb, gameID)
                    else:
                        gameOver = await get_game_finish(mlb, game.gamepk)
                    if gameOver:
                        summary = f'FINAL: {player} {player_stats}'
                        player_attributes[f'{player}']['In Progress'] = False
                        player_attributes[f'{player}']['Old Summary'] = summary
                        if message:
                            await message.delete()
                            player_attributes[f'{player}']['Message'] = await channel.send(summary)
                        else:
                            player_attributes[f'{player}']['Message'] = await channel.send(summary)
                    elif player_attributes[f'{player}']['Old Summary'] != summary and invalidStats == False:
                        player_attributes[f'{player}']['Old Summary'] = summary
                        if message:
                            await message.delete()
                            player_attributes[f'{player}']['Message'] = await channel.send(summary)
                        else:
                            player_attributes[f'{player}']['Message'] = await channel.send(summary)
                    break

@tasks.loop(minutes=30)
async def update_prices(channel):
    PriceTool = TheShowPrices()
    for player in players:
        uuid = player_uuids[f'{player}']
        alert_type = player_attributes[f'{player}']['Type']
        data = await PriceTool.fetch(f'https://mlb24.theshow.com/apis/listing.json?uuid={uuid}')
        if alert_type == 'Buy':
            current_price = data['best_buy_price']
            desired_price = player_attributes[f'{player}']['Price']
            if current_price <= desired_price:
                if player_attributes[f'{player}']['Allow Alerts']:
                    await channel.send(f'BUY ALERT: {player} is under {desired_price} stubs!')
                    player_attributes[f'{player}']['Allow Alerts'] = False
            elif current_price > desired_price:
                player_attributes[f'{player}']['Allow Alerts'] = True
        elif alert_type == 'Sell':
            current_price = data['best_sell_price']
            desired_price = player_attributes[f'{player}']['Price']
            if current_price >= desired_price:
                if player_attributes[f'{player}']['Allow Alerts']:
                    await channel.send(f'SELL ALERT: {player} is over {desired_price} stubs!')
                    player_attributes[f'{player}']['Allow Alerts'] = False
            elif current_price < desired_price:
                player_attributes[f'{player}']['Allow Alerts'] = True
    await PriceTool.close()


@bot.event
async def on_ready():
    channel = bot.get_channel(996715384365396038) # Channel to send updates in
    price_alerts = bot.get_channel(1107027549382516766) # Channel to send price updates in
    update.start(channel)
    restart_loop.start(channel)
    update_prices.start(price_alerts)

@bot.event
async def setup_hook():
    global current_date
    global schedule
    current_date = date.today()
    schedule = await get_schedule(mlb)
    PriceTool = TheShowPrices()
    await main(PriceTool)
    await loadData()

bot.run(TOKEN)