import mlbstatsapi
from datetime import datetime, date

mlb = mlbstatsapi.Mlb()
player = mlb.get_people_id("Tyler O'Neill")
schedule = mlb.get_scheduled_games_by_date(date.today())
status = mlb.get_game(746654)
summary = mlb.get_game_box_score(746249).teams.away.players[f"id{641933}"].stats['batting']

# Kenley Jansen GAME ID: 746249 PLAYER ID: 445276
# Tyler O'Neill: GAME ID: 746249 PLAYER ID: 641933

print(summary)