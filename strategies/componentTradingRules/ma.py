# coding: utf-8
# autor:Eden
# date:2018-07-31
# ma.py : implement Moving Average(MA) that describe in the 'Complex stock trading strategy based on parallel particle swarm optimization'
# parameters: nl: long-period moving average lenth :[15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
#			  ns: short-period moving average lenth :[1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200 ]
# singal: buy signal : short-period moving average above  long-period moving average
#		  sell signal : short-period moving average below  long-period moving average
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np


def score(row):
	if (row['smas'] == np.nan) or (row['smal'] == np.nan):
		return 0.0
	if row['buy']:		
		return 1.0
	if row['sell']:
		return -1.0
	return 0.0

def ma(code, nl=[15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250], ns= [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200]):
	stockData = utils.getStockData(code)
	cnt = 0
	scoreRes = pd.DataFrame()
	for l in nl:
		for s in ns:
			if l > s:
				smal = pd.Series(stockData['adjclose'].rolling(l).mean().values, index = stockData['datetime'])
				smas = pd.Series(stockData['adjclose'].rolling(s).mean().values, index = stockData['datetime'])
				cnt = cnt + 1
				# print smal, smas
				buy =  smas > smal
				sell =  smas < smal
				result = pd.concat([smal,smas, buy, sell], keys = ['smal','smas', 'buy', 'sell'], axis = 1)
				# print result
				# result.apply (lambda row: score(row),axis=1)
				scoreRes['score' + str(s) + '_' + str(l)] = result.apply (lambda row: score(row),axis=1)
	print scoreRes	
	print "total Strategy: " + str(cnt)			

if __name__=="__main__":
	ma("5" )