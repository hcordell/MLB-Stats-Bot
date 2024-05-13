import mlbstatsapi
from datetime import datetime, date

mlb = mlbstatsapi.Mlb()
player = mlb.get_people_id("Cristian Javier")
schedule = mlb.get_scheduled_games_by_date('2024-05-13')
status = mlb.get_game_box_score(745512).teams.home.players['id668804']
status = status.stats['batting']
t = mlb.get_game(747040)['gamedata']['datetime']['time']
if mlb.get_game_box_score(745755).teams.home.players['id624647'].stats['batting'] != None:
    print('true')
summary = mlb.get_game_box_score(746404).teams.home.players[f"id{664299}"].stats['pitching']['blownsaves']
# Kenley Jansen GAME ID: 746977 PLAYER ID: 445276
# Tyler O'Neill: GAME ID: 746249 PLAYER ID: 641933

print(t[0])