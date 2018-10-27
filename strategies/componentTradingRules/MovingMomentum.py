# coding: utf-8
# autor:Eden
# date:2018-07-31
# ma.py : implement Macd Histogram that describe in the https://stockcharts.com/school/doku.php?id=chart_school:trading_strategies:moving_momentum
# parameters: hnl: Moving histogram long-period moving average lenth :[15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
#			  hns: Moving histogram  short-period moving average lenth :[1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200 ]
#			  ht: Moving histogram  t-days EMA of MACD		
# 			snl: Simple MA long-period moving average lenth :[15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
#			  sns: Simple MA  short-period moving average lenth :[1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200 ]
#			  ht: Moving histogram  t-days EMA of MACD				
#			sto_n: STO look-back period length :[5, 10, 15, 20, 25, 50, 75, 100, 125, 150, 200, 250]
#			  sto_m: STO smoothing period length : [3, 7, 11]
#			  sto_ob: STO overbought threshold : [80, 85, 90]
#			  sto_os: STO oversold threshold : [20, 25, 30]
# singal: buy signal : when the value from negitive to postive
#		  sell signal : when the value from postive to negitive
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
import math

class MacdHistogram:
	def __init__(self):
		self.strategyName = "MacdHistogram"

	#use to parse the result that return by the backtest run. "ns_nl_t" pattern
	def parseparams(self, para):
		nl = []
		ns = []
		t = []
		temPara = para.split('_')
		t.append(int(temPara[-1]))
		nl.append(int(temPara[-2]))
		ns.append(int(temPara[-3]))
		return {'nl': nl, 'ns': ns, 'time': t}

	def defaultParam(self):
		ns = range(8, 21, 1) # 13
		nl = range(24, 40, 2) #8
		t = range(8, 15, 1) # 6
		# ns = [12]
		# nl = [26]		
		# t = [9]		
		parms = {'nl': nl, 'ns': ns, 'time': t}
		return parms

	def score(self, row):
		if (math.isnan(row['prediverse'])) or (math.isnan(row['diverse'])):
			return 0.0
		if row['prediverse'] < 0 and row['diverse'] > 0 :		
			return 1.0
		if row['prediverse'] > 0 and row['diverse'] < 0 :		
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
		time = kwargs.get('time')
		for l in nl:
			for s in ns:
				for t in time:
					if len(stockData) <= l - 1:
						continue
					smal = pd.Series(stockData['adjclose'].ewm(span = l).mean().values, index = stockData['datetime'])
					smas = pd.Series(stockData['adjclose'].ewm(span = s).mean().values, index = stockData['datetime'])
					macd = smal -smas
					signalLine = macd.ewm(span = t).mean()
					diverse = macd - signalLine
					prediverse = diverse.shift(-1)
					buy =  smas > smal
					sell =  smas < smal
					result = pd.concat([prediverse,diverse], keys = ['prediverse','diverse'], axis = 1)
					scoreRes[str(s) + '_' + str(l) + '_' + str(t)] = result.apply (lambda row: self.score(row),axis=1)
					cnt = cnt + 1
		# print "total Strategy: " + str(cnt)		
		# print scoreRes
		return scoreRes, cnt	

if __name__=="__main__":
	stockDataTrain = utils.getStockDataTrain("0005", True)
	ma = MacdHistogram()
	params = ma.defaultParam()
	ma.run(stockDataTrain, **params)
