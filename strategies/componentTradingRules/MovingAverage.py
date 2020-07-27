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
import math

class MovingAverage:
	def __init__(self):
		self.strategyName = "MovingAverage"

	#use to parse the result that return by the backtest run. "ns_nl" pattern
	def parseparams(self, para):
		n = []
		k = []
		temPara = para.split('_')
		n.append(int(temPara[-1]))
		k.append(int(temPara[-2]))
		return {'nl': n, 'ns': k}

	def defaultParam(self):
		nl = list(range(15, 255, 5))
		ns_small = list(range(1, 10, 1))
		ns_big = list(range(10, 200, 5))
		ns = ns_small + ns_big
		parms = {'nl': nl, 'ns': ns}
		return parms

	def score(self, row):
		if (math.isnan(row['smas'])) or (math.isnan(row['smal'])):
			return 0.0
		if row['buy']:		
			return 1.0
		if row['sell']:
			return -1.0
		return 0.0
	
	def checkParams(self, **kwargs):
		if 0 == len(kwargs):
			return False
		nl = kwargs.get('nl')
		ns = kwargs.get('ns')
		if nl[0] <= ns[0]:
			return False
		else:
			return True			

	def run(self, stockData, **kwargs):
		cnt = 0
		scoreRes = pd.DataFrame()
		nl = kwargs.get('nl')
		ns = kwargs.get('ns')
		for l in nl:
			for s in ns:
				if l > s:
					if len(stockData) <= l - 1:
						continue
					result = self.calculate(stockData, l, s)
					cnt = cnt + 1
					scoreRes[str(s) + '_' + str(l)] = \
					result.apply (lambda row: self.score(row),axis=1)
		return scoreRes, cnt	

	#return the smal, smas, buy and sell so that it can be used in other algorithm	
	def calculate(self, stockData, l, s):
		smal = pd.Series(stockData['adjclose'].rolling(l).mean().values, index = stockData['datetime'])
		smas = pd.Series(stockData['adjclose'].rolling(s).mean().values, index = stockData['datetime'])
		# cnt = cnt + 1
		buy =  smas > smal
		sell =  smas < smal
		result = pd.concat([smal,smas, buy, sell], keys = ['smal','smas', 'buy', 'sell'], axis = 1)
		return result


if __name__=="__main__":
	stockDataTrain = utils.getStockDataTrain("0005", True)
	ma = MovingAverage()
	params = ma.defaultParam()
	ma.run(stockDataTrain, **params)



	