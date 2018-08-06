# coding: utf-8
# autor: Eden
# date: 2018-08-03
# rsi.py :  Relative Strength Index is a very popular oversold/overbought indicator which measures the velocity and magnitude of directional price movements
#			An n day RSI of a trading day t is calculated as follows:RSI = 100 - 100/(1+Avg.U/Avg.D)
#			AvgU:is the average of all up price moves.比如第二天比第一天上浮，将上浮的值计算出来，然后全部加合后，取平均值。，
#			AvgD:is the average of all down price moves
#			RSI oscillates between 0 and 100. RSI is considered overbought when above a high threshold such as 70 and oversold when below a low threshold such as 30
#			
# parameters: n: look-back period length :[11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
#			  ob: overbought threshold : [80, 75, 70]
#			  os: oversold threshold : [20, 25, 30]
# Suppose the close price of trading day t is pt
# singal: buy signal :  RSI rises back above the oversold threshold
#		  sell signal : RSI falls back below the overbought threshold.
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
import math

def calcUp(closeList):
	i = 1
	allSum = 0.0
	while i < len(closeList):
		if closeList[i] > closeList[i-1]:
			allSum = allSum + (closeList[i] - closeList[i-1])
		i = i + 1			
	return allSum/len(closeList)


def calcDown(closeList):
	i = 1
	allSum = 0.0
	while i < len(closeList):
		if closeList[i] < closeList[i-1]:
			allSum = allSum + (closeList[i-1] - closeList[i])
		i = i + 1			
	return allSum/len(closeList)


def score(row, b, s):
	if math.isnan(row['rsi']):
		return 0.0
	# RSI rises back above the oversold threshold; buy
	if row['rsi'] > s:
		return 1.0
	# RSI falls back below the overbought threshold; sell
	if row['adjclose'] < b:
		return -1.0
	return 0.0

def rsi(code, n = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20], \
	ob = [80, 75, 70], os = [20, 25, 30]):
	stockData = utils.getStockData(code)
	cnt = 0
	scoreRes = pd.DataFrame()
	for i in n:
		aveU = pd.Series(stockData['adjclose'].rolling(i).apply(calcUp,raw=True).values, index = stockData['datetime'])
		# print aveU
		aveD = pd.Series(stockData['adjclose'].rolling(i).apply(calcDown,raw=True).values, index = stockData['datetime'])
		rsi = 100 - 100/(1+(aveU.values/aveD.values))
		stockData['rsi'] = rsi
		# print stockData
		for b in ob:
			for s in os:
				stockData['score' + str(i) + '_' + str(b) + '_' + str(s)] = stockData.apply (lambda row: score(row, b , s),axis=1)
				cnt = cnt + 1
		# print stockData
	print "total Strategy: " + str(cnt)			

if __name__=="__main__":
	rsi("5")