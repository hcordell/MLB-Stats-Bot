import requests
import mlbstatsapi
import json
from datetime import date
mlb = mlbstatsapi.Mlb()

url = 'https://statsapi.mlb.com/api/v1.1/game/778120/feed/live'
response = requests.get(url)
data = response.json()

data2 = mlb.get_game(778120)
schedule = mlb.get_scheduled_games_by_date('2025-04-28')
print(data2)

for id in data['liveData']['boxscore']['teams']['away']['players']:
    try:
        print(data['liveData']['boxscore']['teams']['away']['players'][id]['person']['fullName'])
        print(data['liveData']['boxscore']['teams']['away']['players'][id]['stats']['batting']['summary'])
    except:
        print('No batting stats')


