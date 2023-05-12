import aiohttp
import asyncio

player_list = {}

async def start_session():
    player_list['Session'] = session = aiohttp.ClientSession()
    yield
    await session.close()

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()

async def main():
    async with player_list['Session'].get() as session:
        for x in range(1, 74):
            data = await fetch(session, f'https://mlb23.theshow.com/apis/listings.json?type=mlb_card&page={x}&series_id=1337')
            for y in range(25):
                try:
                    player_list[f"{data['listings'][y]['listing_name']}"] = f"{data['listings'][y]['item']['uuid']}"
                except:
                    break
    print(player_list['Gerrit Cole'])

asyncio.run(main())