# coding: utf-8
# autor: Eden
# date: 2018-08-03
# rsi.py :  Relative Strength Index is a very popular oversold/overbought indicator which measures the velocity and magnitude of directional price movements
#			An n day RSI of a trading day t is calculated as follows:RSI = 100 - 100/(1+Avg.U/Avg.D)
#			AvgU:is the average of all up price moves
#			AvgD:is the average of all down price moves
#			RSI oscillates between 0 and 100. RSI is considered overbought when above a high threshold such as 70 and oversold when below a low threshold such as 30
#			
# parameters: n: look-back period length :[11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
#			  ob: overbought threshold : [80, 75, 70]
#			  os: oversold threshold : [20, 25, 30]
# Suppose the close price of trading day t is pt
# singal: buy signal :  RSI falls back below the oversold threshold
#		  sell signal : RSI rasie back below the overbought threshold.
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
import talib


def score(row, b, s):
	if (row['middle'] == np.nan):
		return 0.0
	# when today's adjclose is the highest price to buy
	if row['adjclose'] < row['lower']:
		return 1.0
	# when today's adjclose is the lowest price to 	sell
	if row['adjclose'] > row['upper']:
		return -1.0
	return 0.0

def rsi(code, n = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20], \
	ob = [80, 75, 70], os = [20, 25, 30]):
	stockData = utils.getStockData(code)
	cnt = 0
	scoreRes = pd.DataFrame()
	for i in n:
			rsi = talib.RSI
			aveD = pd.Series(stockData['adjclose'].rolling(i).mean().values, index = stockData['datetime'])
			for time in k:
				upper = ave + time * std
				lower = ave - time * std
				result = pd.concat([pd.Series(stockData['adjclose'].values, index = stockData['datetime']), ave, lower, upper], keys = ['adjclose','middle', 'lower', 'upper'], axis = 1)
				
				result['score' + str(i) + '_' +str(time)] = result.apply (lambda row: score(row),axis=1)
				print result
				# score['score' + str(i) + '_' +str(time)] = result['score' + str(i) + '_' +str(time)]
				cnt = cnt + 1
				# print score
	print "total Strategy: " + str(cnt)			

if __name__=="__main__":
	rsi("5", [10], [1.5])