# coding: utf-8
# autor:Eden
# date:2018-07-31
# obva.py : On-Balance Volume Average, a volume based trading rule in our universe of component rules of PRS.
#			OBVA is the same as MA except that OBVA calculates moving average with stock volume instead of stock price.
# parameters: nl: long-period moving average lenth :[5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
#			  ns: short-period moving average lenth :[1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200]
# singal: buy signal : short-period moving average above  long-period moving average
#		  sell signal : short-period moving average below  long-period moving average
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
import math

class OnBalanceVolAve:
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
		nl=[5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
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

	# def run(code, nl=[5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250], ns= [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200]):
	def run(self, stockData, **kwargs):
		# stockData = utils.getStockData(code)
		cnt = 0
		scoreRes = pd.DataFrame()
		nl = kwargs.get('nl')
		ns = kwargs.get('ns')
		for l in nl:
			for s in ns:
				if l > s:
					smal = pd.Series(stockData['volume'].rolling(l).mean().values, index = stockData['datetime'])
					smas = pd.Series(stockData['volume'].rolling(s).mean().values, index = stockData['datetime'])
					cnt = cnt + 1
					# print smal, smas
					buy =  smas > smal
					sell =  smas < smal
					result = pd.concat([smal,smas, buy, sell], keys = ['smal','smas', 'buy', 'sell'], axis = 1)
					scoreRes[str(s) + '_' + str(l)] = result.apply (lambda row: self.score(row),axis=1)
		# print scoreRes	
		# print "total Strategy: " + str(cnt)			
		return scoreRes, cnt


if __name__=="__main__":
	obva("5")