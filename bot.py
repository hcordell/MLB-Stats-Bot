# bot.py
import os
import discord
import mlbstatsapi
import functools
import asyncio
import aiohttp
import typing
import certifi
import logging
import sys
from datetime import datetime, date
from dotenv import load_dotenv
from string import capwords
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PASSWORD = os.getenv('PASSWORD')

uri = f"mongodb+srv://Chimaezss:{PASSWORD}@mlbstatsbotdb.wcpwbzb.mongodb.net/?retryWrites=true&w=majority&appName=MLBStatsBotDB"
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
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def fetch(self, url):
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API request failed with status {response.status}: {url}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Connection error when fetching {url}: {str(e)}")
            return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout when fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when fetching {url}: {str(e)}")
            return None
    
    async def close(self):
        if not self.session.closed:
            await self.session.close()

async def loadData():
    try:
        player_collection = client.players.players
        try:
            docs = player_collection.find()
            player_list = await docs.to_list(length=None)
            
            for player in player_list:
                try:
                    players.add(player['Name'])
                    player_attributes[f'{player["Name"]}'] = player['Attributes']
                    player_attributes[f'{player}']['Game ID'] = None
                    player_attributes[f'{player}']['In Progress'] = True
                    player_attributes[f'{player}']['Start Time'] = None
                    player_attributes[f'{player}']['AM/PM'] = None
                    player_attributes[f'{player}']['Message'] = None
                    player_attributes[f'{player}']['Team'] = None
                except KeyError as e:
                    logger.error(f"Missing key in player data: {str(e)}")
                except Exception as e:
                    logger.error(f"Error processing player from database: {str(e)}")
            
            logger.info(f"Loaded {len(players)} players from database")
        except Exception as e:
            logger.error(f"Error querying database: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in loadData: {str(e)}")

async def main(PriceTool):
    try:
        for x in range(1, 74):
            try:
                data = await PriceTool.fetch(f'https://mlb25.theshow.com/apis/listings.json?type=mlb_card&page={x}&series_id=1337')
                if not data:
                    logger.error(f"Failed to fetch data for page {x}")
                    continue
                
                for y in range(25):
                    try:
                        player_name = capwords(f"{data['listings'][y]['listing_name']}")
                        player_uuids[f"{player_name}"] = f"{data['listings'][y]['item']['uuid']}"
                    except (KeyError, IndexError):
                        # End of listings for this page
                        break
                    except Exception as e:
                        logger.error(f"Error processing player on page {x}, index {y}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing page {x}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in main function: {str(e)}")
    finally:
        try:
            await PriceTool.close()
        except Exception as e:
            logger.error(f"Error closing PriceTool in main: {str(e)}")

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
    try:
        schedule = mlb.get_scheduled_games_by_date(date.today())
        return schedule
    except Exception as e:
        logger.error(f"Error getting schedule for {date.today()}: {str(e)}")
        return []

@unblock
def get_game_finish(mlb, gameID):
    try:
        status = mlb.get_game(gameID).metadata.gameevents
        if 'game_finished' in status:
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking if game {gameID} is finished: {str(e)}")
        return False

@unblock
def get_status(mlb, player, playerID, gameID):
    try:
        if player_attributes[f'{player}']['Team'] == 'Home':
            try:
                status = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].gamestatus.iscurrentpitcher
            except Exception as e:
                logger.error(f"Error getting Home status for {player} (ID: {playerID}) in game {gameID}: {str(e)}")
                status = None
                player_attributes[f'{player}']['Team'] = 'Unknown'
        elif player_attributes[f'{player}']['Team'] == 'Away':
            try:
                status = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].gamestatus.iscurrentpitcher
            except Exception as e:
                logger.error(f"Error getting Away status for {player} (ID: {playerID}) in game {gameID}: {str(e)}")
                status = None
                player_attributes[f'{player}']['Team'] = 'Unknown'
        else:
            try:
                status = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].gamestatus.iscurrentpitcher
            except Exception:
                try:
                    status = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].gamestatus.iscurrentpitcher
                except Exception as e:
                    logger.error(f"Error finding status for {player} (ID: {playerID}) in game {gameID}: {str(e)}")
                    status = None
        return status
    except Exception as e:
        logger.error(f"Unexpected error in get_status for {player} in game {gameID}: {str(e)}")
        return None

@unblock
def get_stats(mlb, gameID, player, playerID, position):
    """
    Retrieves player statistics from a specific game.
    
    Args:
        mlb: MLB API client instance
        gameID: ID of the game to retrieve stats from
        player: Player name
        playerID: MLB player ID
        position: Position of the player ('batting' or 'pitching')
    
    Returns:
        String containing player stats summary or None if stats not available
    """
    try:
        # Check if player is on home team
        if player_attributes[f'{player}']['Team'] == 'Home':
            try:
                # Get stats for player on home team
                game = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats[position]
                if game != None:
                    player_attributes[f'{player}']['Game ID'] = gameID
                    summary = game['summary']
            except Exception as e:
                # Log error and reset team if home stats not found
                logger.error(f"Error getting Home stats for {player} (ID: {playerID}) in game {gameID}: {str(e)}")
                player_attributes[f'{player}']['Team'] = None
                print('Summary not available. Resetting team.')
                return None
        # Check if player is on away team
        elif player_attributes[f'{player}']['Team'] == 'Away':
            try:
                # Get stats for player on away team
                game = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats[position]
                if game != None:
                    player_attributes[f'{player}']['Game ID'] = gameID
                    summary = game['summary']
            except Exception as e:
                # Log error and reset team if away stats not found
                logger.error(f"Error getting Away stats for {player} (ID: {playerID}) in game {gameID}: {str(e)}")
                player_attributes[f'{player}']['Team'] = None
                print('Summary not available. Resetting team.')
                return None
        # If team is unknown, try both home and away
        else:
            try:
                # Try home team first
                game = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats[position]
                if game != None:
                    player_attributes[f'{player}']['Game ID'] = gameID
                summary = game['summary']
                player_attributes[f'{player}']['Team'] = 'Home'
            except Exception as home_e:
                try:
                    # Try away team if home team fails
                    game = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats[position]
                    if game != None:
                        player_attributes[f'{player}']['Game ID'] = gameID
                    summary = game['summary']
                    player_attributes[f'{player}']['Team'] = 'Away'
                except Exception as e:
                    try:
                        # If player not found in either team but ID exists, store game time info
                        if str(e)[1:3] != 'id':
                            player_attributes[f'{player}']['Game ID'] = gameID
                            game_data = mlb.get_game(gameID)['gamedata']['datetime']
                            player_attributes[f'{player}']['Start Time'] = game_data['time']
                            player_attributes[f'{player}']['AM/PM'] = game_data['ampm']
                    except Exception as time_e:
                        logger.error(f"Error getting game time for {player} in game {gameID}: {str(time_e)}")
                    
                    # Log error if player not found in game
                    logger.error(f"Error finding {player} (ID: {playerID}) in game {gameID}: {str(e)}")
                    print(f'Error: wrong game or violation ({player})')
                    print(f'{e}\n')
                    player_attributes[f'{player}']['Team'] = 'Unknown'
                    return None
        
        # Process summary if available
        if summary:
            player_attributes[f'{player}']['Game ID'] = gameID
            try:
                # Check if game is finished
                status = mlb.get_game(gameID)['metadata']['gameevents']
                if 'game_finished' in status:
                    finished = True
                else:
                    finished = False
                
                # Add save/blown save info for pitchers in finished games
                if position == 'pitching' and finished:
                    try:
                        # Try to get save stats from away team
                        bsv = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats['pitching']['blownsaves']
                        sv = mlb.get_game_box_score(gameID).teams.away.players[f"id{playerID}"].stats['pitching']['saves']
                    except Exception:
                        try:
                            # Try to get save stats from home team
                            bsv = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats['pitching']['blownsaves']
                            sv = mlb.get_game_box_score(gameID).teams.home.players[f"id{playerID}"].stats['pitching']['saves']
                        except Exception as e:
                            logger.error(f"Error getting pitching stats for {player} in game {gameID}: {str(e)}")
                            bsv = 0
                            sv = 0
                    
                    # Add save/blown save to summary
                    if bsv == 1:
                        summary += ', 1 BSV'
                    elif sv == 1:
                        summary += ', 1 SV'
            except Exception as e:
                logger.error(f"Error checking game status for {player} in game {gameID}: {str(e)}")
            
            return summary
        return None
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error in get_stats for {player} in game {gameID}: {str(e)}")
        return None

@bot.command() # Bot command to create a buy alert for a player
@commands.has_role('Admins')
async def buy(ctx, *name):
    if ctx.channel.id == 1109551093081448508 or ctx.channel.id == 1103511198474960916: # Channel to send commands in
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

                # Add player to database
                await client.players.players.insert_one({
                    'Name': player,
                    'Attributes': player_attributes[f'{player}']
                })
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
            if update.is_running():
                update.cancel()
            players.remove(player)
            player_attributes.pop(player)
            await client.players.players.delete_one({'Name': f'{player}'})
            await ctx.send('Success: player removed')
            channel = bot.get_channel(996715384365396038)
            update.start(channel)
        else:
            await ctx.send('Error: player not found')

@bot.command() # Bot command to print player list
async def list(ctx, *args):
    if ctx.channel.id == 1109551093081448508 or isinstance(ctx.channel, discord.channel.DMChannel): # Channel to send commands in
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
        if len(players) == 0:
            await ctx.send('Error: list is empty')
        else:
            for player in players:
                alert_type = player_attributes[f'{player}']['Type']
                price = player_attributes[f'{player}']['Price']
                price_list.append(f'[{alert_type}] {player}: {price}')
            await user.send('\n'.join(price_list))

@bot.command() # Bot command to display help information
async def help_bot(ctx, *args):
    if ctx.channel.id == 1109551093081448508 or isinstance(ctx.channel, discord.channel.DMChannel):
        help_message = [
            "**MLB Stats Bot Commands**",
            "```",
            "!buy [player name] [price] - Create a buy alert for a player",
            "!sell [player name] [price] - Create a sell alert for a player",
            "!remove [player name] - Remove a player from tracking",
            "!list - Show all tracked players",
            "!prices - DM you the current price alerts",
            "!status - Check bot status",
            "!refresh - Refresh schedule and player data",
            "!help_bot - Show this help message",
            "```"
        ]
        await ctx.send("\n".join(help_message))

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
        player_attributes[f'{player}']['Start Time'] = None
        player_attributes[f'{player}']['AM/PM'] = None
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

@bot.command() # Bot command to check bot status
@commands.has_role('Admins')
async def status(ctx, *args):
    try:
        if ctx.channel.id == 1109551093081448508 or ctx.channel.id == 1103511198474960916 or isinstance(ctx.channel, discord.channel.DMChannel):
            status_message = []
            status_message.append("**Bot Status Report**")
            
            # Check tasks
            status_message.append(f"Update task running: {update.is_running()}")
            status_message.append(f"Update prices task running: {update_prices.is_running()}")
            status_message.append(f"Restart loop task running: {restart_loop.is_running()}")
            status_message.append(f"Heartbeat task running: {heartbeat.is_running()}")
            
            # Check data
            status_message.append(f"Players tracked: {len(players)}")
            status_message.append(f"Player UUIDs loaded: {len(player_uuids)}")
            status_message.append(f"Schedule games: {len(schedule)}")
            
            # Check uptime
            if hasattr(bot, 'start_time'):
                uptime = datetime.now() - bot.start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                status_message.append(f"Uptime: {hours}h {minutes}m {seconds}s")
            
            await ctx.send("\n".join(status_message))
    except Exception as e:
        logger.error(f"Error in status command: {str(e)}")
        await ctx.send(f"Error getting status: {str(e)}")

@bot.command() # Bot command to refresh schedule
@commands.has_role('Admins')
async def refresh(ctx, *args):
    try:
        if ctx.channel.id == 1109551093081448508 or ctx.channel.id == 1103511198474960916:
            await ctx.send("Refreshing schedule and player data...")
            
            # Refresh schedule
            global schedule
            try:
                new_schedule = await get_schedule(mlb)
                if new_schedule:
                    schedule = new_schedule
                    await ctx.send(f"Schedule refreshed with {len(schedule)} games")
                else:
                    await ctx.send("Failed to refresh schedule")
            except Exception as e:
                logger.error(f"Error refreshing schedule: {str(e)}")
                await ctx.send(f"Error refreshing schedule: {str(e)}")
            
            # Refresh player UUIDs
            try:
                PriceTool = TheShowPrices()
                await main(PriceTool)
                await ctx.send(f"Player UUIDs refreshed, now tracking {len(player_uuids)} players")
            except Exception as e:
                logger.error(f"Error refreshing player UUIDs: {str(e)}")
                await ctx.send(f"Error refreshing player UUIDs: {str(e)}")
            
            # Update last refresh time for the update task
            update.last_schedule_update = date.today().strftime("%Y-%m-%d")
            
            await ctx.send("Refresh complete")
    except Exception as e:
        logger.error(f"Error in refresh command: {str(e)}")
        await ctx.send(f"Error during refresh: {str(e)}")

@tasks.loop(hours=1)
async def db_backup():
    try:
        player_db = client.players
        player_collection = player_db.players
        docs = []
        
        for player in players:
            try:
                doc = await player_collection.find_one({'Name': player})
                if doc:
                    updates = {'$set': {'Attributes': player_attributes[f'{player}']}}
                    await player_collection.update_one({'Name': player}, updates)
                else:
                    doc = {
                        'Name': player,
                        'Attributes': player_attributes[f'{player}']
                    }
                    docs.append(doc)
            except Exception as e:
                logger.error(f"Error backing up player {player}: {str(e)}")
        
        if len(docs) != 0:
            await player_collection.insert_many(docs)
    except Exception as e:
        logger.error(f"Error in db_backup: {str(e)}")

@tasks.loop(minutes=1)
async def restart_loop(channel):
    try:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        if current_time == '03:00':
            logger.info("Daily restart triggered")
            try:
                player_db = client.players
                player_collection = player_db.players
                docs = []
                
                for player in players:
                    try:
                        doc = await player_collection.find_one({'Name': player})
                        player_attributes[f'{player}']['Game ID'] = None
                        player_attributes[f'{player}']['In Progress'] = True
                        player_attributes[f'{player}']['Start Time'] = '0:00'
                        player_attributes[f'{player}']['AM/PM'] = None
                        player_attributes[f'{player}']['Message'] = None
                        player_attributes[f'{player}']['Team'] = None
                        
                        if doc:
                            updates = {'$set': {'Attributes': player_attributes[f'{player}']}}
                            await player_collection.update_one({'Name': player}, updates)
                        else:
                            doc = {
                                'Name': player,
                                'Attributes': player_attributes[f'{player}']
                            }
                            docs.append(doc)
                    except Exception as e:
                        logger.error(f"Error updating player {player} in database during restart: {str(e)}")
                
                if len(docs) != 0:
                    try:
                        await player_collection.insert_many(docs)
                    except Exception as e:
                        logger.error(f"Error inserting new players during restart: {str(e)}")
                
                logger.info("Database updated, starting new bot instance")
                os.startfile('bot.py')
                await bot.close()
            except Exception as e:
                logger.error(f"Error during restart process: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in restart_loop: {str(e)}")

@tasks.loop(minutes=5)
async def update(channel):
    try:
        logger.info('Update in progress')
        global schedule
        
        # Check if we need to refresh the schedule (once per day)
        current_date = date.today()
        today = current_date.strftime("%Y-%m-%d")
        if not hasattr(update, 'last_schedule_update') or update.last_schedule_update != today:
            logger.info(f"Refreshing schedule for {today}")
            try:
                new_schedule = await get_schedule(mlb)
                if new_schedule:  # Only update if we got a valid schedule
                    schedule = new_schedule
                    update.last_schedule_update = today
                    logger.info(f"Schedule updated with {len(schedule)} games")
            except Exception as e:
                logger.error(f"Failed to refresh schedule: {str(e)}")
                return  # Exit early if schedule refresh fails
        
        cur_time = int(datetime.now().strftime('%H')) % 12
        cur_ampm = datetime.now().strftime('%p')
        
        for player in players:
            try:
                logger.info(f'Updating {player}')
                await asyncio.sleep(30)
                player_id = player_attributes[f'{player}']['Player ID']
                position = player_attributes[f'{player}']['Position']
                gameID = player_attributes[f'{player}']['Game ID']
                message = player_attributes[f'{player}']['Message']
                invalidStats = False
                
                if not player_attributes[f'{player}']['In Progress']:
                    continue  # Skip players not in progress
                
                for game in schedule:
                    try:
                        if 'Start Time' in player_attributes[f'{player}']:
                            logger.info(f'Player: {player}\nStart Time: {player_attributes[f"{player}"]["Start Time"]}')
                            if cur_ampm == 'AM' and player_attributes[f'{player}']['AM/PM'] == 'PM' and not cur_time <= 2:
                                break
                            elif cur_ampm == player_attributes[f'{player}']['AM/PM']:
                                if cur_ampm == 'PM' and cur_time == 0:
                                    cur_time += 1
                                if int(player_attributes[f'{player}']['Start Time'][0]) > cur_time:
                                    break
                        
                        # Fetch player stats with retry mechanism
                        player_stats = None
                        for attempt in range(3):  # Try up to 3 times
                            try:
                                if gameID:
                                    player_stats = await get_stats(mlb, gameID, player, player_id, position)
                                else:
                                    player_stats = await get_stats(mlb, game.gamepk, player, player_id, position)
                                break
                            except Exception as e:
                                logger.warning(f"Stats fetch attempt {attempt + 1} failed for {player}: {str(e)}")
                                if attempt == 2:  # Last attempt
                                    logger.error(f"Failed to fetch stats for {player} after 3 attempts")
                                    continue
                                await asyncio.sleep(5)  # Wait before retry
                        
                        if player_stats and player_attributes[f'{player}']['Position'] == 'pitching':
                            await asyncio.sleep(10)
                            status = None
                            for attempt in range(3):  # Try up to 3 times
                                try:
                                    status = await get_status(mlb, player, player_id, game.gamepk)
                                    break
                                except Exception as e:
                                    logger.warning(f"Status fetch attempt {attempt + 1} failed for {player}: {str(e)}")
                                    if attempt == 2:  # Last attempt
                                        logger.error(f"Failed to fetch status for {player} after 3 attempts")
                                        continue
                                    await asyncio.sleep(5)  # Wait before retry
                        else:
                            status = None
                        
                        if not player_stats:
                            continue  # Skip if no stats available
                        
                        player_attributes[f'{player}']['In Progress'] = True
                        if player_stats == '0-0' or player_stats == '0.0 IP, 0 ER, 0 K, 0 BB':
                            invalidStats = True
                        
                        # Construct summary message
                        summary = f'{player}: {player_stats}'
                        
                        # Check game status with retry
                        gameOver = None
                        for attempt in range(3):  # Try up to 3 times
                            try:
                                if gameID:
                                    gameOver = await get_game_finish(mlb, gameID)
                                else:
                                    gameOver = await get_game_finish(mlb, game.gamepk)
                                break
                            except Exception as e:
                                logger.warning(f"Game finish check attempt {attempt + 1} failed for {player}: {str(e)}")
                                if attempt == 2:  # Last attempt
                                    logger.error(f"Failed to check game finish for {player} after 3 attempts")
                                    continue
                                await asyncio.sleep(5)  # Wait before retry
                        
                        if gameOver is None:
                            continue  # Skip if game status check failed
                        
                        if gameOver:
                            summary = f'FINAL: {player} {player_stats}'
                            player_attributes[f'{player}']['In Progress'] = False
                            player_attributes[f'{player}']['Old Summary'] = summary
                            
                            for msg_attempt in range(3):  # Try up to 3 times to delete and send messages
                                try:
                                    if message:
                                        await message.delete()
                                    player_attributes[f'{player}']['Message'] = await channel.send(summary)
                                    break
                                except Exception as e:
                                    logger.error(f"Message handling attempt {msg_attempt + 1} failed for {player}: {str(e)}")
                                    if msg_attempt == 2:  # Last attempt
                                        logger.error(f"Failed to handle messages for {player} after 3 attempts")
                                        player_attributes[f'{player}']['Message'] = None
                                    await asyncio.sleep(5)  # Wait before retry
                        
                        elif player_attributes[f'{player}']['Old Summary'] != summary and not invalidStats:
                            player_attributes[f'{player}']['Old Summary'] = summary
                            
                            for msg_attempt in range(3):  # Try up to 3 times to delete and send messages
                                try:
                                    if message:
                                        await message.delete()
                                    player_attributes[f'{player}']['Message'] = await channel.send(summary)
                                    break
                                except Exception as e:
                                    logger.error(f"Message handling attempt {msg_attempt + 1} failed for {player}: {str(e)}")
                                    if msg_attempt == 2:  # Last attempt
                                        logger.error(f"Failed to handle messages for {player} after 3 attempts")
                                        player_attributes[f'{player}']['Message'] = None
                                    await asyncio.sleep(5)  # Wait before retry
                        
                        break  # Successfully processed this player, move to next
                    except Exception as game_e:
                        logger.error(f"Error processing game for {player}: {str(game_e)}")
                        continue
            except Exception as player_e:
                logger.error(f"Error updating player {player}: {str(player_e)}")
                continue
    except Exception as e:
        logger.error(f"Unexpected error in update task: {str(e)}")
        # Try to restart the task if it fails
        if update.is_running():
            update.restart()

@tasks.loop(minutes=30)
async def update_prices(channel):
    PriceTool = None
    try:
        logger.info("Starting price updates")
        PriceTool = TheShowPrices()
        
        for player in players:
            try:
                if player not in player_uuids:
                    logger.warning(f"No UUID found for player {player}, skipping price update")
                    continue
                    
                uuid = player_uuids[f'{player}']
                alert_type = player_attributes[f'{player}']['Type']
                
                data = await PriceTool.fetch(f'https://mlb25.theshow.com/apis/listing.json?uuid={uuid}')
                if not data:
                    logger.error(f"Failed to fetch price data for {player}")
                    continue
                
                if alert_type == 'Buy':
                    try:
                        current_price = data['best_buy_price']
                        desired_price = player_attributes[f'{player}']['Price']
                        
                        if current_price <= desired_price:
                            if player_attributes[f'{player}']['Allow Alerts']:
                                try:
                                    await channel.send(f'BUY ALERT: {player} is under {desired_price} stubs!')
                                    player_attributes[f'{player}']['Allow Alerts'] = False
                                except Exception as e:
                                    logger.error(f"Error sending buy alert for {player}: {str(e)}")
                        elif current_price > desired_price:
                            player_attributes[f'{player}']['Allow Alerts'] = True
                    except KeyError as e:
                        logger.error(f"Missing key in price data for {player}: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error processing buy price for {player}: {str(e)}")
                
                elif alert_type == 'Sell':
                    try:
                        current_price = data['best_sell_price']
                        desired_price = player_attributes[f'{player}']['Price']
                        
                        if current_price >= desired_price:
                            if player_attributes[f'{player}']['Allow Alerts']:
                                try:
                                    await channel.send(f'SELL ALERT: {player} is over {desired_price} stubs!')
                                    player_attributes[f'{player}']['Allow Alerts'] = False
                                except Exception as e:
                                    logger.error(f"Error sending sell alert for {player}: {str(e)}")
                        elif current_price < desired_price:
                            player_attributes[f'{player}']['Allow Alerts'] = True
                    except KeyError as e:
                        logger.error(f"Missing key in price data for {player}: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error processing sell price for {player}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error updating prices for player {player}: {str(e)}")
                continue
                
        logger.info("Price updates completed")
    except Exception as e:
        logger.error(f"Unexpected error in update_prices task: {str(e)}")
    finally:
        if PriceTool:
            try:
                await PriceTool.close()
            except Exception as e:
                logger.error(f"Error closing PriceTool: {str(e)}")

@tasks.loop(minutes=15)
async def heartbeat():
    try:
        logger.info("Heartbeat: Bot is running")
        
        # Check if other tasks are running
        if not update.is_running():
            logger.warning("Update task is not running, restarting it")
            channel = bot.get_channel(996715384365396038)
            update.start(channel)
        
        if not update_prices.is_running():
            logger.warning("Update_prices task is not running, restarting it")
            price_alerts = bot.get_channel(1107027549382516766)
            update_prices.start(price_alerts)
        
        if not restart_loop.is_running():
            logger.warning("Restart_loop task is not running, restarting it")
            channel = bot.get_channel(996715384365396038)
            restart_loop.start(channel)
    except Exception as e:
        logger.error(f"Error in heartbeat: {str(e)}")

@bot.event
async def on_ready():
    try:
        bot.start_time = datetime.now()
        logger.info(f"Bot connected as {bot.user.name}")
        channel = bot.get_channel(996715384365396038) # Channel to send updates in
        price_alerts = bot.get_channel(1107027549382516766) # Channel to send price updates in
        
        # Start all background tasks
        if not update.is_running():
            update.start(channel)
        
        if not restart_loop.is_running():
            restart_loop.start(channel)
        
        if not update_prices.is_running():
            update_prices.start(price_alerts)
        
        if not heartbeat.is_running():
            heartbeat.start()
        
        if not db_backup.is_running():
            db_backup.start()
            
        logger.info("All background tasks started")
    except Exception as e:
        logger.error(f"Error in on_ready: {str(e)}")

@bot.event
async def setup_hook():
    try:
        logger.info("Bot starting up, initializing data...")
        global schedule
        
        try:
            schedule = await get_schedule(mlb)
            logger.info(f"Schedule loaded with {len(schedule)} games")
        except Exception as e:
            logger.error(f"Error loading schedule: {str(e)}")
            schedule = []
        
        try:
            PriceTool = TheShowPrices()
            await main(PriceTool)
            logger.info(f"Loaded {len(player_uuids)} player UUIDs")
        except Exception as e:
            logger.error(f"Error loading player UUIDs: {str(e)}")
        
        try:
            await loadData()
            logger.info(f"Loaded {len(players)} players from database")
        except Exception as e:
            logger.error(f"Error loading player data: {str(e)}")
        
        logger.info("Bot setup complete")
    except Exception as e:
        logger.error(f"Critical error during bot setup: {str(e)}")

bot.run(TOKEN)