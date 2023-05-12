import aiohttp
import asyncio

player_uuids = {}

class TheShowPrices:
    def __init__(self) -> None:
        self.session = aiohttp.ClientSession()

    async def fetch(self, url):
        async with self.session.get(url) as response:
            return await response.json()
    
    async def close(self):
        await self.session.close()

async def main():
    PriceTool = TheShowPrices()
    for x in range(1, 74):
        data = await PriceTool.fetch(f'https://mlb23.theshow.com/apis/listings.json?type=mlb_card&page={x}&series_id=1337')
        for y in range(25):
            try:
                player_uuids[f"{data['listings'][y]['listing_name']}"] = f"{data['listings'][y]['item']['uuid']}"
            except:
                break
    await PriceTool.close()
    print(player_uuids['Gerrit Cole'])

asyncio.run(main())