# coding: utf-8
# autor: Eden
# date: 2018-08-03
# sto.py :  momentum indicator.Stochastic Oscillator. The calculation of STO involves the high, low and close price in a look-back period n.
#			STO = 100*(Pt - Pl)/(Ph - Pl); Pt - the close price of day t.STO --> %K;
#			%D: %D = 3-day SMA of %K
#			plowest and phihgest is the lowest low and highest high price in the look-back period n
#			For an increasing price trend, pt is close to phighest so STO is close to 100.
#			Conversely, STO is close to 0 for a declining price trend.	
# parameters: n: look-back period length :[5, 10, 15, 20, 25, 50, 75, 100, 125, 150, 200, 250]
#			  m: smoothing period length : [3, 7, 11]
#			  ob: overbought threshold : [80, 85, 90]
#			  os: oversold threshold : [20, 25, 30]
# singal: buy signal :  when fast %D line is below the oversold threshold os and 
#						accompanied with that the fast %K line rises above the fast %D line
#		  sell signal : when fast %D line is above the overbought threshold ob and 
#						accompanied with that the the fast %K line falls below the fast %D line.

import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
import math


def score(row, b, s):
	if (math.isnan(row['sto'])) or (math.isnan(row['_D'])):
		return 0.0
	if (row['_D'] < s) and (row['sto'] > row['_D']):		
		return 1.0
	if (row['_D'] > b) and (row['sto'] < row['_D']):
		return -1.0
	return 0.0

def sto(code, n=[5, 10, 15, 20, 25, 50, 75, 100, 125, 150, 200, 250], m= [3, 7, 11],\
				ob = [80, 85, 90], os = [20, 25, 30]):
	stockData = utils.getStockData(code)
	cnt = 0
	scoreRes = pd.DataFrame()
	for t in n:
		for k in m:
			stockData['lowest' + str(t)] = stockData['low'].rolling(t).min()
			stockData['highest' + str(t)] = stockData['high'].rolling(t).max()
			stockData['sto'] = 100 * (stockData['close'] - stockData['lowest' + str(t)])/(stockData['highest' + str(t)] - stockData['lowest' + str(t)])
			stockData['_D'] = stockData['sto'].rolling(k).mean()
			for b in ob:
				for s in os:
					stockData['score' + str(t) + '_' + str(k) + '_' + str(b) + '_' + str(s)] = stockData.apply (lambda row: score(row, b , s),axis=1)
					cnt = cnt + 1
	# print stockData					
	print "total Strategy: " + str(cnt)			

if __name__=="__main__":
	# sto("5",[5],[3],[80],[20] )
	sto("5")