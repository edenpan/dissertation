# coding: utf-8
# autor:Eden
# date:2018-08-03
# bb.py : Bollinger Bands is a volatility indicator that considers the fluctuations of stock price. 
#			middle band: BBs calculates an n day moving average of past close price Avgt,n.
#			upper band: k times above the standard deviation of the middle band.
#			lower band: k times below the standard deviation of the middle band.
# parameters: n: moving average length :[10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 75, 80, 90, 100, 125, 150, 175, 200, 250]
#			  k: multiplier :[1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]
# Suppose the close price of trading day t is pt
# singal: buy signal : the close price fall below the lower band
#		  sell signal : a sell signal is generated when the close price is above the upper band
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np


def score(row):
	if (row['middle'] == np.nan):
		return 0.0
	# when today's adjclose is the highest price to buy
	if row['adjclose'] < row['lower']:
		return 1.0
	# when today's adjclose is the lowest price to 	sell
	if row['adjclose'] > row['upper']:
		return -1.0
	return 0.0

def checkParam(n):
	for i in n:
		if i <= 1:
			raise Exception("parameters input error, %s less than 2", i)

def BollingerBands(code, n = [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 75, 80, 90, 100, 125, 150, 175, 200, 250], \
	k = [1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]):

	stockData = utils.getStockData(code)
	cnt = 0
	scoreRes = pd.DataFrame()
	checkParam(n)
	for i in n:
			ave = pd.Series(stockData['adjclose'].rolling(i).mean().values, index = stockData['datetime'])
			std = pd.Series(stockData['adjclose'].rolling(i).std().values, index = stockData['datetime'])
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
	BollingerBands("5", [10], [1.5])