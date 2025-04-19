import mlbstatsapi

def get_game_finish(mlb):
    try:
        gameID = 778268
        status = mlb.get_game(gameID).metadata.gameevents
        if 'game_finished' in status:
            print('Game finished')
        print(status)
    except Exception as e:
        print(e)

mlb = mlbstatsapi.Mlb() # Initalize MLB API

get_game_finish(mlb)
