import mlbstatsapi
import statsapi
import time

mlb = mlbstatsapi.Mlb()
stats = ['season']
groups = ['hitting']

gameIDs = []

for game in mlb.get_scheduled_games_by_date('2023-05-04'):
    gameIDs.append(game.gamepk)

print(mlb.get_game_box_score(718317).teams.home.players['id682928'].gamestatus.iscurrentbatter)