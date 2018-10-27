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

class StochasticOscillator:

	def __init__(self):
		self.strategyName = "StochasticOscillatorStrategy"


	#para is the form like : n_m_ob_os
	def parseparams(self, para):
		n = []
		m = []
		ob = []
		os = []
		temPara = para.split('_')
		n.append(int(temPara[-4]))
		m.append(int(temPara[-3]))
		ob.append(int(temPara[-2]))
		os.append(int(temPara[-1]))
		return {'n': n, 'ob': ob, 'os': os, 'm': m}

	def defaultParam(self):
		n = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
		m = [3, 7, 11]
		ob = [80, 75, 70]
		os = [20, 25, 30]
		parms = {'n': n, 'ob': ob, 'os': os, 'm': m}
		return parms

	def checkParams(self, **kwargs):
		if 0 == len(kwargs):
			return False
			
		return True


	def score(self,row, b, s):
		if (math.isnan(row['sto'])) or (math.isnan(row['_D'])):
			return 0.0
		if (row['_D'] < s) and (row['sto'] > row['_D']):		
			return 1.0
		if (row['_D'] > b) and (row['sto'] < row['_D']):
			return -1.0
		return 0.0

	def run(self, stockData, **kwargs):
		cnt = 0
		scoreRes = pd.DataFrame()
		n = kwargs.get('n')
		m = kwargs.get('m')
		ob = kwargs.get('ob')
		os = kwargs.get('os')
		for t in n:
			for k in m:
				stockData['lowest' + str(t)] = stockData['low'].rolling(t).min()
				stockData['highest' + str(t)] = stockData['high'].rolling(t).max()
				stockData['sto'] = 100 * (stockData['close'] - stockData['lowest' + str(t)])/(stockData['highest' + str(t)] - stockData['lowest' + str(t)])
				stockData['_D'] = stockData['sto'].rolling(k).mean()
				for b in ob:
					for s in os:
						scoreRes[str(t) + '_' + str(k) + '_' + str(b) + '_' + str(s)] = stockData.apply (lambda row: self.score(row, b , s),axis=1)
						cnt = cnt + 1
		# print stockData	
		scoreRes['datetime'] = 	stockData['datetime']
		scoreRes = scoreRes.set_index('datetime')				
		# print "total Strategy: " + str(cnt)		
		return scoreRes, cnt	

if __name__=="__main__":
	stockDataTrain = utils.getStockDataTrain("0005", True)
	sto = StochasticOscillator()
	params = sto.defaultParam()
	sto.run(stockDataTrain, **params)

