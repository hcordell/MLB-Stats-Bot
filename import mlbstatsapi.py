import mlbstatsapi
from datetime import datetime, date

mlb = mlbstatsapi.Mlb()
player = mlb.get_people_id("Tyler O'Neill")
schedule = mlb.get_scheduled_games_by_date('2024-04-11')
status = mlb.get_game(746977)
summary = mlb.get_game_box_score(746977).teams.home.players[f"id{445276}"].stats['pitching']
# Kenley Jansen GAME ID: 746977 PLAYER ID: 445276
# Tyler O'Neill: GAME ID: 746249 PLAYER ID: 641933

print(summary)