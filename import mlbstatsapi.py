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
print(mlb.get_people_id('Ronald Acuna Jr.'))
print(mlb.get_game_box_score(gameIDs[8]).teams.home.players['id660670'].stats)

# for id in gameIDs:
#     failCount = 0
#     while True:
#         try:
#             full_game = mlb.get_game_play_by_play(id)
#         except:
#             failCount += 1
#             if failCount == 3:
#                 break
#             else:
#                 continue
#         for play in full_game.allplays:
#             print(play.result.description)
#         break