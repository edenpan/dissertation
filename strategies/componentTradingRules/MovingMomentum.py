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

class MovingMomentum:
	def __init__(self):
		self.strategyName = "MovingMomentum"

	#use to parse the result that return by the backtest run.
	# str(hl) + '_' + str(hs) + '_' + str(ht) + '_' + str(sl) + '_' + str(ss) + '_' + str(stn) + str(stm) + '_' + str(stob) + '_' + str(stos)
	def parseparams(self, para):
		hl = []
		hs = []
		ht = []
		sl = []
		ss = []
		stn = []
		stm = []
		stob = []
		stos = []
		temPara = para.split('_')

		hl.append(int(temPara[-9]))
		hs.append(int(temPara[-8]))
		ht.append(int(temPara[-7]))
		sl.append(int(temPara[-6]))
		ss.append(int(temPara[-5]))
		stn.append(int(temPara[-4]))
		stm.append(int(temPara[-3]))
		stob.append(int(temPara[-2]))
		stos.append(int(temPara[-1]))
		return {'hns': hs, 'hnl': hl, 'htime': ht, 'snl': sl, 'sns': ss, 'sto_n': stn, 'sto_m': stm, 'sto_ob': stob, 'sto_os': stos}

	def defaultParam(self):
		# ns = range(8, 21, 1) # 13
		# nl = range(24, 40, 2) #8
		# t = range(8, 15, 1) # 6
		# hns = [12]
		# hnl = [26]		
		# htime = [9]		
		# snl = [40]
		# sns = [30]
		# sto_n = [3]
		# sto_m = [7]
		# sto_ob = [75]
		# sto_os = [25]
		hns = range(8, 12) 
		hnl = range(24, 40, 2) 
		htime = range(8, 15, 1)
		snl = range(15, 255, 5)
		sns = range(1, 10, 1) + range(10, 200, 5)
		sto_n = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
		sto_m = [3, 7, 11]
		sto_ob = [80, 75, 70]
		sto_os = [20, 25, 30]
		parms = {'hns': hns, 'hnl': hnl, 'htime': htime, 'snl': snl, 'sns': sns, 'sto_n': sto_n, 'sto_m':sto_m, 'sto_ob': sto_ob, 'sto_os': sto_os}
		return parms

	def score(self, row, ob, os):
		if (math.isnan(row['prediverse'])) or (math.isnan(row['diverse'])) \
		or (math.isnan(row['smas'])) or (math.isnan(row['smal'])) \
		or (math.isnan(row['sto'])) or (math.isnan(row['sto_k'])):
			return 0.0

		if row['prediverse'] < 0 and row['diverse'] > 0 \
		and row['smas'] > row['smal'] \
		and row['sto'] > row['sto_k'] and row['sto_k'] < os :		
			return 1.0
		if row['prediverse'] > 0 and row['diverse'] < 0 \
		and row['smas'] < row['smal'] \
		and row['sto'] < row['sto_k'] and row['sto_k'] > ob :	
			return -1.0

		return 0.0
	
	def checkParams(self, **kwargs):
		if 0 == len(kwargs):
			return False
		snl = kwargs.get('snl')
		sns = kwargs.get('sns')
		if snl[0] <= sns[0]:
			return False

		hns = kwargs.get('hns')
		hnl = kwargs.get('hnl')
		if hnl[0] <= hns[0]:
			return False
		
		return True			

	def run(self, stockData, **kwargs):
		cnt = 0
		scoreRes = pd.DataFrame()
		hnl = kwargs.get('hnl')
		hns = kwargs.get('hns')
		htime = kwargs.get('htime')
		snl = kwargs.get('snl')
		sns = kwargs.get('sns')
		sto_n = kwargs.get('sto_n')
		sto_m = kwargs.get('sto_m')
		sto_ob = kwargs.get('sto_ob')
		sto_os = kwargs.get('sto_os')
		for hl in hnl:
			for hs in hns:
				for ht in htime:
					for sl in snl:
						for ss in sns:
							for stn in sto_n:
								for stm in sto_m:
									if (len(stockData) <= hl - 1) or (len(stockData) <= sl - 1) :
										continue
									smal = pd.Series(stockData['adjclose'].rolling(sl).mean().values, index = stockData['datetime'])
									smas = pd.Series(stockData['adjclose'].rolling(ss).mean().values, index = stockData['datetime'])
									emal = pd.Series(stockData['adjclose'].ewm(span = hl, min_periods=0,adjust=False,ignore_na=False).mean().values, index = stockData['datetime'])
									emas = pd.Series(stockData['adjclose'].ewm(span = hs, min_periods=0,adjust=False,ignore_na=False).mean().values, index = stockData['datetime'])
									macd = emal -emas
									signalLine = macd.ewm(span = ht).mean()
									diverse = macd - signalLine
									prediverse = diverse.shift(-1)
									stoLowest = stockData['low'].rolling(stn).min()
									stoHighest = stockData['high'].rolling(stn).max()
									sto = 100 * (stockData['close'] - stoLowest)/(stoHighest - stoLowest)
									sto.index = list(stockData['datetime'])
									sto_k = sto.rolling(stm).mean()
									result = pd.concat([diverse,prediverse, smal, smas, sto, sto_k], keys = ['diverse','prediverse', 'smal', 'smas', 'sto', 'sto_k'], axis = 1)
									for stob in sto_ob:
										for stos in sto_os:
											# useful = str(hl) + '_' + str(hs) + '_' + str(ht) + '_' + str(sl) + '_' + str(ss) + '_' + str(stn) + '_' + str(stm) + '_' + str(stob) + '_' + str(stos)
											scoreRes[str(hl) + '_' + str(hs) + '_' + str(ht) + '_' + str(sl) + '_' + str(ss) + '_' + str(stn) + '_' + str(stm) + '_' + str(stob) + '_' + str(stos)] = result.apply (lambda row: self.score(row, stob , stos),axis=1)
									# print "cnt: " + str(cnt)
									cnt = cnt + 1
		# print "total Strategy: " + str(cnt)		
		# print scoreRes
		return scoreRes, cnt	

if __name__=="__main__":
	stockDataTrain = utils.getStockDataTrain("0005", True)
	mm = MovingMomentum()
	params = mm.defaultParam()
	mm.run(stockDataTrain, **params)
