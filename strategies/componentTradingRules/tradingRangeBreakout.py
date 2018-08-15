# coding: utf-8
# autor:Eden
# date:2018-07-31
# tradingRangeBreakout.py : It calculates the highest and lowest close price of past n days as follows:
#							Ht,n =max(pt−1,pt−2,...,pt−n), the t's days previous n th days highest price
#							Lt,n =min(pt−1,pt−2,...,pt−n),the t's days previous n th days lowest price
# parameters: nl: long-period moving average lenth :[15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
#			  ns: short-period moving average lenth :[1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200 ]
# Suppose the close price of trading day t is pt
# singal: buy signal : pt > Ht,n
#		  sell signal : pt < Lt,n
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
from baseStrategy import baseStrategy

# class tradingRangeBreakoutStrat(baseStrategy):
def score(row):
	if (row['highest'] == np.nan) or (row['lowest'] == np.nan):
		return 0.0
	# when today's adjclose is the highest price to buy
	if row['adjclose'] == row['highest']:
		return 1.0
	# when today's adjclose is the lowest price to 	sell
	if row['adjclose'] == row['lowest']:
		return -1.0
	return 0.0

def checkParam(n):
	for i in n:
		if i <= 1:
			raise Exception("parameters input error, %s less than 2", i)

def tradingRangeBreakout(code, n = [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 75, 80, 90, 100, 125, 150, 175, 200, 250]):
	stockData = utils.getStockData(code)
	cnt = 0
	scoreRes = pd.DataFrame()
	checkParam(n)
	for i in n:
			highest = pd.Series(stockData['adjclose'].rolling(i).max().values, index = stockData['datetime'])
			lowest = pd.Series(stockData['adjclose'].rolling(i).min().values, index = stockData['datetime'])
			cnt = cnt + 1
			result = pd.concat([pd.Series(stockData['adjclose'].values, index = stockData['datetime']), highest, lowest], keys = ['adjclose','highest','lowest'], axis = 1)
			# print result
			scoreRes['score' + str(i)] = result.apply (lambda row: score(row),axis=1)
	print scoreRes	
	print "total Strategy: " + str(cnt)			

if __name__=="__main__":
	tradingRangeBreakout("5")