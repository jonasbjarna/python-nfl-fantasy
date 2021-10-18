#from espn_api.football import League
import requests
import json
import sys
import datetime
import pprint
from collections import OrderedDict

'''
https://fantasy.espn.com/football/team?leagueId=1237784&teamId=1&seasonId=2020
#'''

class NFLFantasyInstance():
	def __init__(self, league_id):
		self.load_initial_config(league_id)
		#testing printing output
		#self.print_configs()

	def load_initial_config(self, league_id):
		config = {
				#Úrvalsdeildin, BB Kings
				1237784:
				{
					'team_id':1,
					'team_name': 'BB Kings',
					'league_name': 'Úrvalsdeildin'
				},
				#League of extraordinary gentlement
				#'''
				280587:
				{
					'team_id': 11,
					'team_name': 'Bromma Bro',
					'league_name': 'League of Extraordinary Gents'
				}
				#'''
		}
		self.team_id = config[league_id]['team_id']
		self.league_id = league_id
		self.swid = <SWID>
		self.espn_s2 = <ESPN_S2>
		self.year = 2020
		self.URI = 'https://fantasy.espn.com/apis/v3/games/ffl/seasons/' + str(self.year) + '/segments/0/leagues/' + str(self.league_id)
		self.team_name = config[league_id]['team_name']
		self.league_name = config[league_id]['league_name']

	def print_configs(self):
		print('team_id: %s' % self.team_id)
		print('swid: %s' % self.swid)
		print('espn_s2: %s' % self.espn_s2)
		print('URI: %s' % self.URI)

	'''
	The routine returns a dict of available D/STs on waivers as well as current D/ST
	with stats for current matchup, including rank of the attack and average points 
	against opponent D/STs.
	'''
	def get_available_defenses(self, is_debug_mode, week_number = None):
		#get NFL matchups for this week
		matchups = self.get_nfl_matchups(is_debug_mode, week_number)

		'''
		with following filters we get available D/STs (filterSlotIds: 16), ie with status 'FREEAGENT'  or 'WAIVERS'
		Instead we want to get all D/STs and filter out later because we also want to include current
		D/ST in the routine
		'''
		#filters = {"players":{"filterStatus":{"value":["FREEAGENT","WAIVERS"]},"filterSlotIds":{"value":[16]}}}
		views = ['kona_player_info']
		filters = {"players":{"filterSlotIds":{"value":[16]}}}
		data = self.get_request(views, is_debug_mode, filters)

		#here we get both available D/ST (status: FREEAGENT, WAIVERS) and my current D/ST (onTeamId: self.team_id)
		#will not return teams on bye
		players = [item for item in data['players'] if item['status'] in ['FREEAGENT','WAIVERS'] or item['onTeamId'] == self.team_id]
		print('Number of D/STs obtained (FREEAGENT, WAIVERS, current D/ST): %d' % len(players))

		#get the free agent D/ST (note only is correct when include filterSlotIds in request)
		'''
		free_agents_ids = [str(item['player']['proTeamId']) for item in data['players']]
		print('free_agents_ids: %s' % free_agents_ids)
		'''
		
		'''
		for the available D/ST, get the opponents and their statistics
		Put each D/ST in defenses dict, each item in defenses will contains 
		all the info needed and look like as follows:
		{ '1': { 'fullName': 'Falcons D/ST',
		         'homeAway': 'home',
		         'id': '1',
		         'name': 'Atlanta Falcons',
		         'opponent_average': 3.0,
		         'opponent_id': '29',
		         'opponent_name': 'CAR',
		         'opponent_reverse_rank': 20,
		         'positionalRanking': 31,
		         'totalRating': -5.0},
		'''
		defense_ratings_dict = data['positionAgainstOpponent']['positionalRatings']['16']['ratingsByOpponent']
		defenses = {}

		for item in players:
			#use the info for team from matchups dict
			team_id = str(item['player']['proTeamId'])
			if team_id in matchups.keys():
				defenseTmp = matchups[team_id]
				defenseTmp['positionalRanking'] = item['ratings']['0']['positionalRanking']
				defenseTmp['totalRating'] = item['ratings']['0']['totalRating']
				defenseTmp['fullName'] = item['player']['fullName']

				#add the info from defense_ratings_dict for opponent id

				opponent = defense_ratings_dict[defenseTmp['opponent_id']]
				defenseTmp['opponent_average'] = opponent['average']
				#make the rank reverse so in terms of how highly you want it
				defenseTmp['opponent_reverse_rank'] = 33 - opponent['rank']

				#add current D/ST to dict of D/STs.
				defenses[team_id] = defenseTmp
			#remove the key if d/st not playing?
			else:
				print('Team %s (%s) might have a bye, not in matchups dict' % (team_id, self.get_team_by_index(int(team_id))))

		print('\n** Sorted defenses for team %s in league %s' % (self.team_name, self.league_name))
		for d in sorted(defenses.items(), key = lambda item: item[1]['opponent_reverse_rank']):
			pprint.pprint(d[1], indent = 2)

		#print('## defenses_sorted')
		#pprint.pprint(defenses_sorted, indent = 2)

	def get_request(self, views, is_debug_mode, filters):
		if filters:
			headers = {'x-fantasy-filter': json.dumps(filters)}
			response = requests.get(self.URI,
				cookies={"swid": self.swid,
					"espn_s2": self.espn_s2}, params={"view": views}, headers = headers)
		else:
			response = requests.get(self.URI,
				cookies={"swid": self.swid,
					"espn_s2": self.espn_s2}, params={"view": views})			
		data = response.json()
		if is_debug_mode:
			jdata = json.dumps(data, indent = 2)
			print('jdata: %s' % jdata)

		return data

	'''
	Get matchups for an NFL week;
	for current week (week_number = None) unless week_number is specified
	The routine returns a dict with team_id as key and both ids and names of both teams in matchup as values
	'''
	def get_nfl_matchups(self, is_debug_mode, week_number = None):
		base_uri = 'http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
		
		#if week_number specified then get the matchups for that particular week 
		if week_number:
			append_uri = '?week=' + str(week_number)
			base_uri += append_uri

		'''
		Get the matchups for the NFL week specified. 
		Create a dict with id for each team as key, opponent as values,
		and homeAway value if team is playing at home or away
		'''
		response = requests.get(base_uri)
		data = response.json()
		if is_debug_mode:
			results = json.dumps(data, indent = 2)
			print('matchups: %s' % results)

		matchups = {}
		events = data['events']

		#get the matchups in a dict (keys: home team index, value: away team index)
		matches_dict = {}
		for event in events:
			ht = str(self.get_team_index_by_name(event['shortName'].split('@')[0].strip()))
			at = str(self.get_team_index_by_name(event['shortName'].split('@')[1].strip()))
			matches_dict[ht] = at
			matches_dict[at] = ht

		#create a dict with team_id as key and both team_ids and names as values
		for event in events:
			#get the teams competing in the event
			competitors = event['competitions'][0]['competitors']
			for comp in competitors:
				team = {}
				team['id'] = comp['id']
				team['homeAway'] = comp['homeAway']
				team['name'] = comp['team']['displayName']
				team['opponent_id'] = matches_dict[comp['id']]
				team['opponent_name'] = self.get_team_by_index(int(matches_dict[comp['id']]))
				matchups[comp['id']] = team

		if is_debug_mode:
			print('NFL matchups this week..')
			pprint.pprint(matchups, indent = 2)

		return matchups


	def get_team_by_index(self, team_index):
		TEAMS_MAP = {
		    0 : 'None',
		    1 : 'ATL',
		    2 : 'BUF',
		    3 : 'CHI',
		    4 : 'CIN',
		    5 : 'CLE',
		    6 : 'DAL',
		    7 : 'DEN',
		    8 : 'DET',
		    9 : 'GB',
		    10: 'TEN',
		    11: 'IND',
		    12: 'KC',
		    13: 'LV', #changed from 'OAK'
		    14: 'LAR',
		    15: 'MIA',
		    16: 'MIN',
		    17: 'NE',
		    18: 'NO',
		    19: 'NYG',
		    20: 'NYJ',
		    21: 'PHI',
		    22: 'ARI',
		    23: 'PIT',
		    24: 'LAC',
		    25: 'SF',
		    26: 'SEA',
		    27: 'TB',
		    28: 'WSH',
		    29: 'CAR',
		    30: 'JAX',
		    33: 'BAL',
		    34: 'HOU'
		}
		return TEAMS_MAP[team_index]

	def get_team_index_by_name(self, team_name):
		TEAMS_MAP = {
			'ATL': 1,
			'BUF': 2,
			'CHI': 3,
			'CIN': 4,
			'CLE': 5,
			'DAL': 6,
			'DEN': 7,
			'DET': 8,
			'GB' : 9,
			'TEN': 10,
			'IND': 11,
			'KC' : 12,
			'LV': 13, #changed from 'OAK'
			'LAR': 14,
			'MIA': 15,
			'MIN': 16,
			'NE' : 17,
			'NO' : 18,
			'NYG': 19,
			'NYJ': 20,
			'PHI': 21,
			'ARI': 22,
			'PIT': 23,
			'LAC': 24,
			'SF' : 25,
			'SEA': 26,
			'TB' : 27,
			'WSH': 28,
			'CAR': 29,
			'JAX': 30,
			'BAL': 33,
			'HOU': 34
		}
		return TEAMS_MAP[team_name]


if __name__ == '__main__':
	'''
	Handle print statements for logging
	'''

	week_number = 16
	week_number_str = 'week ' + str(week_number) if week_number else 'current week'

	filename_tmp = 'Response output - '
	timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
	#datetime_sec = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
	filename = filename_tmp + week_number_str + ' - ' + timestamp + '.txt'
	filename_output = open(filename, 'a', encoding = 'utf-8')
	sys.stdout = filename_output

	#Úrvalsdeildin, BB Kings
	#league_id = 1237784
	#League of extraordinary gentlement, Bromma Bro.
	#league_id = 280587

	is_debug_mode = False
	league_ids = [1237784, 280587]
	for league_id in league_ids:
		instance = NFLFantasyInstance(league_id)
		print('\nNow starting method get_available_defenses() for team name %s (league: %s) and %s...' % (instance.team_name, instance.league_name, week_number_str))
		instance.get_available_defenses(is_debug_mode, week_number)


	filename_output.close()
