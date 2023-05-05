import mlbstatsapi
import statsapi
import time

mlb = mlbstatsapi.Mlb()
stats = ['season']
groups = ['hitting']

gameIDs = []

for game in mlb.get_scheduled_games_by_date('2023-05-04'):
    gameIDs.append(game.gamepk)

# P ID 516416
print(mlb.get_people_id('Josh Hader'))
print(mlb.get_people_id('Clayton Kershaw'))
print(mlb.get_person(477132).primaryposition.name)
