# coding: utf-8
# autor:Eden
# date:2018-08-03
# macd.py : combination of two exponential moving average (EMA) of close price,
#			weighs current prices more heavily than past prices in the average calculation
#			α : 2/(1+n)
#			E.Avgt,n = α × pt + (1 − α) × E.Avgt−1,n
#			E.Avgt−1,n is the n day EMA of former day t − 1
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
import math

class MovingAveConvergeDiver:
	def __init__(self):
		self.strategyName = "MovingAverageStrategy"

	#use to parse the result that return by the backtest run. "ns_nl" pattern
	def parseparams(self, para):
		n = []
		k = []
		temPara = para.split('_')
		n.append(int(temPara[-1]))
		k.append(int(temPara[-2]))
		return {'nl': n, 'ns': k}

	def defaultParam(self):
		nl=[15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
		ns= [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200]
		parms = {'nl': nl, 'ns': ns}
		return parms
	
	def checkParams(self, **kwargs):
		if 0 == len(kwargs):
			return False			
		nl = kwargs.get('nl')
		ns = kwargs.get('ns')
		if nl[0] <= ns[0]:
			return False
		else:
			return True			
			
	def score(self, row):
		if (math.isnan(row['smas'])) or (math.isnan(row['smal'])):
			return 0.0
		if row['buy']:		
			return 1.0
		if row['sell']:
			return -1.0
		return 0.0

	def run(self, stockData, **kwargs):
		nl = kwargs.get('nl')
		ns = kwargs.get('ns')
		cnt = 0
		scoreRes = pd.DataFrame()
		for l in nl:
			for s in ns:
				if l > s:
					smal = pd.Series(stockData['adjclose'].ewm(span = l, min_periods=0,adjust=False,ignore_na=False), index = stockData['datetime'])
					smas = pd.Series(stockData['adjclose'].ewm(span = s, min_periods=0,adjust=False,ignore_na=False), index = stockData['datetime'])
					cnt = cnt + 1
					# print smal, smas
					buy =  smas > smal
					sell =  smas < smal
					result = pd.concat([smal,smas, buy, sell], keys = ['smal','smas', 'buy', 'sell'], axis = 1)
					# print result
					# result.apply (lambda row: score(row),axis=1)
					# scoreRes[str(i) + '-' +str(time)] = result.apply (lambda row: self.score(row),axis=1)
					scoreRes[str(s) + '_' + str(l)] = result.apply (lambda row: self.score(row),axis=1)
		# print scoreRes	
		# print "total Strategy: " + str(cnt)		
		return scoreRes, cnt

if __name__=="__main__":
	macd("5" )