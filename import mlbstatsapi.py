import mlbstatsapi
from datetime import datetime, date

mlb = mlbstatsapi.Mlb()
player = mlb.get_people_id("Cristian Javier")
schedule = mlb.get_scheduled_games_by_date(date.today())
status = mlb.get_game(746404)
summary = mlb.get_game_box_score(746404).teams.home.players[f"id{664299}"].stats['pitching']['blownsaves']
# Kenley Jansen GAME ID: 746977 PLAYER ID: 445276
# Tyler O'Neill: GAME ID: 746249 PLAYER ID: 641933

print(summary)