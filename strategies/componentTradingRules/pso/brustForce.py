# coding: utf-8
from numpy import *
import random
from math import sin, sqrt
from backtest import runbackTest
import sys
sys.path.append('../')
import utils
import copy
import importlib

class Bruteforce:
	def setStockData(self, code, isTrain):
		self.stockData = utils.getStockDataTrain(code, isTrain)
	
	def setStrategy(self, strategyName, params=None):
		module = importlib.import_module(strategyName)
		class_ = getattr(module, strategyName)
		strategy = class_()
		self.strategyName = strategy.strategyName
		self.strategy = strategy
		if params is None:
			self.searchParams = strategy.defaultParam()
		else:
			# self.searchParams = strategy.parseparams(params)
			self.searchParams = params
		self.dimensions = len(self.searchParams)

	def run(self):
		bStratRes, bBstRes = runbackTest(self.stockData, self.strategy, **self.searchParams)
		return bStratRes, bBstRes

if __name__=="__main__":
	

	# # bf.setStrategy("MacdHistogram")
	# # bf.setStrategy("MovingAverage")
	# # bf.setStrategy("MovingAveConvergeDiver")
	# # bf.setStrategy("BollingerBandsStrategy")
	# # bf.setStrategy("StochasticOscillator")
	# # bf.setStrategy("MovingMomentum")

	# bStratRes, bBstRes = bf.run()
	# print bBstRes
	# print bStratRes
	# bf.setStockData("2382", False)
	
	# bf.setStrategy("MacdHistogram", bBstRes[0])
	# bf.setStrategy("StochasticOscillator", bBstRes[0])

	bf = Bruteforce()
	
	outsample = [{'code':'2382','parma':{'snl': [40], 'hnl': [36], 'sto_n': [18], 'hns': [10], 'sto_ob': [80], 'sns': [35], 'sto_os': [30], 'sto_m': [7], 'htime': [8]}},{'code':'175','parma':{'snl': [160], 'hnl': [32], 'sto_n': [14], 'hns': [8], 'sto_ob': [80], 'sns': [125], 'sto_os': [20], 'sto_m': [3], 'htime': [10]}},{'code':'2018','parma':{'snl': [135], 'hnl': [34], 'sto_n': [16], 'hns': [8], 'sto_ob': [80], 'sns': [80], 'sto_os': [20], 'sto_m': [7], 'htime': [11]}},{'code':'700','parma':{'snl': [115], 'hnl': [26], 'sto_n': [14], 'hns': [8], 'sto_ob': [80], 'sns': [95], 'sto_os': [20], 'sto_m': [3], 'htime': [8]}},{'code':'2007','parma':{'snl': [230], 'hnl': [28], 'sto_n': [20], 'hns': [10], 'sto_ob': [80], 'sns': [160], 'sto_os': [20], 'sto_m': [7], 'htime': [11]}},{'code':'388','parma':{'snl': [85], 'hnl': [30], 'sto_n': [20], 'hns': [8], 'sto_ob': [80], 'sns': [75], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'2628','parma':{'snl': [70], 'hnl': [24], 'sto_n': [16], 'hns': [10], 'sto_ob': [80], 'sns': [65], 'sto_os': [25], 'sto_m': [3], 'htime': [14]}},{'code':'2318','parma':{'snl': [135], 'hnl': [34], 'sto_n': [14], 'hns': [8], 'sto_ob': [80], 'sns': [105], 'sto_os': [25], 'sto_m': [7], 'htime': [12]}},{'code':'83','parma':{'snl': [100], 'hnl': [34], 'sto_n': [20], 'hns': [9], 'sto_ob': [70], 'sns': [90], 'sto_os': [25], 'sto_m': [3], 'htime': [12]}},{'code':'823','parma':{'snl': [100], 'hnl': [24], 'sto_n': [11], 'hns': [10], 'sto_ob': [80], 'sns': [90], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'23','parma':{'snl': [110], 'hnl': [30], 'sto_n': [16], 'hns': [9], 'sto_ob': [80], 'sns': [85], 'sto_os': [30], 'sto_m': [7], 'htime': [12]}},{'code':'267','parma':{'snl': [70], 'hnl': [26], 'sto_n': [17], 'hns': [8], 'sto_ob': [75], 'sns': [65], 'sto_os': [20], 'sto_m': [7], 'htime': [11]}},{'code':'2388','parma':{'snl': [120], 'hnl': [28], 'sto_n': [13], 'hns': [10], 'sto_ob': [75], 'sns': [60], 'sto_os': [25], 'sto_m': [11], 'htime': [8]}},{'code':'1928','parma':{'snl': [80], 'hnl': [26], 'sto_n': [14], 'hns': [9], 'sto_ob': [80], 'sns': [75], 'sto_os': [20], 'sto_m': [3], 'htime': [12]}},{'code':'66','parma':{'snl': [60], 'hnl': [36], 'sto_n': [19], 'hns': [8], 'sto_ob': [70], 'sns': [55], 'sto_os': [30], 'sto_m': [7], 'htime': [9]}},{'code':'762','parma':{'snl': [200], 'hnl': [30], 'sto_n': [19], 'hns': [9], 'sto_ob': [80], 'sns': [190], 'sto_os': [25], 'sto_m': [7], 'htime': [10]}},{'code':'27','parma':{'snl': [55], 'hnl': [34], 'sto_n': [19], 'hns': [9], 'sto_ob': [80], 'sns': [45], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'1038','parma':{'snl': [90], 'hnl': [26], 'sto_n': [12], 'hns': [8], 'sto_ob': [80], 'sns': [80], 'sto_os': [20], 'sto_m': [7], 'htime': [10]}},{'code':'883','parma':{'snl': [125], 'hnl': [34], 'sto_n': [17], 'hns': [8], 'sto_ob': [70], 'sns': [120], 'sto_os': [20], 'sto_m': [3], 'htime': [13]}},{'code':'1109','parma':{'snl': [105], 'hnl': [26], 'sto_n': [16], 'hns': [9], 'sto_ob': [80], 'sns': [80], 'sto_os': [20], 'sto_m': [3], 'htime': [12]}},{'code':'12','parma':{'snl': [60], 'hnl': [32], 'sto_n': [13], 'hns': [9], 'sto_ob': [75], 'sns': [45], 'sto_os': [25], 'sto_m': [7], 'htime': [8]}},{'code':'1088','parma':{'snl': [85], 'hnl': [26], 'sto_n': [16], 'hns': [8], 'sto_ob': [80], 'sns': [55], 'sto_os': [20], 'sto_m': [7], 'htime': [10]}},{'code':'2319','parma':{'snl': [40], 'hnl': [34], 'sto_n': [17], 'hns': [9], 'sto_ob': [80], 'sns': [25], 'sto_os': [25], 'sto_m': [3], 'htime': [11]}},{'code':'11','parma':{'snl': [105], 'hnl': [26], 'sto_n': [12], 'hns': [10], 'sto_ob': [80], 'sns': [70], 'sto_os': [20], 'sto_m': [7], 'htime': [11]}},{'code':'1','parma':{'snl': [125], 'hnl': [28], 'sto_n': [11], 'hns': [8], 'sto_ob': [80], 'sns': [115], 'sto_os': [20], 'sto_m': [3], 'htime': [9]}},{'code':'3328','parma':{'snl': [60], 'hnl': [36], 'sto_n': [15], 'hns': [8], 'sto_ob': [75], 'sns': [35], 'sto_os': [20], 'sto_m': [7], 'htime': [8]}},{'code':'288','parma':{'snl': [105], 'hnl': [30], 'sto_n': [12], 'hns': [9], 'sto_ob': [80], 'sns': [95], 'sto_os': [20], 'sto_m': [3], 'htime': [12]}},{'code':'2','parma':{'snl': [60], 'hnl': [26], 'sto_n': [14], 'hns': [9], 'sto_ob': [80], 'sns': [40], 'sto_os': [30], 'sto_m': [7], 'htime': [11]}},{'code':'992','parma':{'snl': [190], 'hnl': [30], 'sto_n': [17], 'hns': [9], 'sto_ob': [80], 'sns': [95], 'sto_os': [30], 'sto_m': [7], 'htime': [14]}},{'code':'1299','parma':{'snl': [80], 'hnl': [32], 'sto_n': [13], 'hns': [8], 'sto_ob': [80], 'sns': [40], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'6','parma':{'snl': [130], 'hnl': [38], 'sto_n': [15], 'hns': [8], 'sto_ob': [80], 'sns': [70], 'sto_os': [30], 'sto_m': [11], 'htime': [10]}},{'code':'386','parma':{'snl': [100], 'hnl': [28], 'sto_n': [20], 'hns': [10], 'sto_ob': [80], 'sns': [95], 'sto_os': [25], 'sto_m': [11], 'htime': [9]}},{'code':'3988','parma':{'snl': [160], 'hnl': [28], 'sto_n': [14], 'hns': [9], 'sto_ob': [80], 'sns': [120], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'17','parma':{'snl': [45], 'hnl': [34], 'sto_n': [12], 'hns': [8], 'sto_ob': [75], 'sns': [10], 'sto_os': [30], 'sto_m': [3], 'htime': [10]}},{'code':'1398','parma':{'snl': [80], 'hnl': [26], 'sto_n': [12], 'hns': [9], 'sto_ob': [80], 'sns': [35], 'sto_os': [20], 'sto_m': [3], 'htime': [9]}},{'code':'688','parma':{'snl': [160], 'hnl': [24], 'sto_n': [15], 'hns': [8], 'sto_ob': [80], 'sns': [65], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'939','parma':{'snl': [85], 'hnl': [30], 'sto_n': [15], 'hns': [8], 'sto_ob': [80], 'sns': [30], 'sto_os': [20], 'sto_m': [11], 'htime': [12]}},{'code':'941','parma':{'snl': [115], 'hnl': [36], 'sto_n': [14], 'hns': [8], 'sto_ob': [80], 'sns': [110], 'sto_os': [20], 'sto_m': [7], 'htime': [10]}},{'code':'1113','parma':{'snl': [40], 'hnl': [24], 'sto_n': [15], 'hns': [8], 'sto_ob': [80], 'sns': [35], 'sto_os': [30], 'sto_m': [3], 'htime': [8]}},{'code':'144','parma':{'snl': [20], 'hnl': [26], 'sto_n': [11], 'hns': [8], 'sto_ob': [80], 'sns': [9], 'sto_os': [30], 'sto_m': [3], 'htime': [14]}},{'code':'16','parma':{'snl': [90], 'hnl': [34], 'sto_n': [15], 'hns': [9], 'sto_ob': [80], 'sns': [65], 'sto_os': [20], 'sto_m': [7], 'htime': [14]}},{'code':'836','parma':{'snl': [110], 'hnl': [30], 'sto_n': [14], 'hns': [8], 'sto_ob': [80], 'sns': [75], 'sto_os': [20], 'sto_m': [3], 'htime': [11]}},{'code':'101','parma':{'snl': [230], 'hnl': [26], 'sto_n': [15], 'hns': [8], 'sto_ob': [80], 'sns': [95], 'sto_os': [30], 'sto_m': [3], 'htime': [11]}},{'code':'5','parma':{'snl': [140], 'hnl': [36], 'sto_n': [12], 'hns': [8], 'sto_ob': [75], 'sns': [120], 'sto_os': [20], 'sto_m': [3], 'htime': [14]}},{'code':'3','parma':{'snl': [60], 'hnl': [34], 'sto_n': [15], 'hns': [8], 'sto_ob': [70], 'sns': [45], 'sto_os': [20], 'sto_m': [3], 'htime': [12]}},{'code':'151','parma':{'snl': [120], 'hnl': [34], 'sto_n': [19], 'hns': [8], 'sto_ob': [70], 'sns': [115], 'sto_os': [20], 'sto_m': [3], 'htime': [10]}},{'code':'19','parma':{'snl': [110], 'hnl': [24], 'sto_n': [15], 'hns': [8], 'sto_ob': [80], 'sns': [95], 'sto_os': [30], 'sto_m': [3], 'htime': [8]}},{'code':'857','parma':{'snl': [80], 'hnl': [28], 'sto_n': [13], 'hns': [8], 'sto_ob': [75], 'sns': [10], 'sto_os': [25], 'sto_m': [3], 'htime': [9]}},{'code':'1044','parma':{'snl': [95], 'hnl': [34], 'sto_n': [20], 'hns': [8], 'sto_ob': [75], 'sns': [70], 'sto_os': [20], 'sto_m': [3], 'htime': [10]}}]
	# outsample = [{'code':'2382','parma':{'ns': [8], 'nl': [32], 'time': [8]}},{'code':'175','parma':{'ns': [8], 'nl': [36], 'time': [8]}},{'code':'2018','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'1928','parma':{'ns': [8], 'nl': [24], 'time': [9]}},{'code':'2318','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'27','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'1109','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'2007','parma':{'ns': [8], 'nl': [24], 'time': [9]}},{'code':'700','parma':{'ns': [8], 'nl': [30], 'time': [8]}},{'code':'388','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'2628','parma':{'ns': [8], 'nl': [28], 'time': [8]}},{'code':'3328','parma':{'ns': [8], 'nl': [30], 'time': [8]}},{'code':'762','parma':{'ns': [8], 'nl': [32], 'time': [8]}},{'code':'267','parma':{'ns': [8], 'nl': [28], 'time': [8]}},{'code':'883','parma':{'ns': [8], 'nl': [30], 'time': [8]}},{'code':'688','parma':{'ns': [9], 'nl': [24], 'time': [8]}},{'code':'836','parma':{'ns': [8], 'nl': [24], 'time': [9]}},{'code':'386','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'2319','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'1088','parma':{'ns': [8], 'nl': [28], 'time': [8]}},{'code':'83','parma':{'ns': [8], 'nl': [30], 'time': [8]}},{'code':'992','parma':{'ns': [17], 'nl': [32], 'time': [8]}},{'code':'939','parma':{'ns': [8], 'nl': [28], 'time': [9]}},{'code':'17','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'3988','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'2388','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'12','parma':{'ns': [8], 'nl': [26], 'time': [9]}},{'code':'288','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'1','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'823','parma':{'ns': [8], 'nl': [30], 'time': [8]}},{'code':'857','parma':{'ns': [8], 'nl': [30], 'time': [8]}},{'code':'941','parma':{'ns': [9], 'nl': [30], 'time': [8]}},{'code':'1299','parma':{'ns': [8], 'nl': [32], 'time': [8]}},{'code':'1398','parma':{'ns': [8], 'nl': [32], 'time': [8]}},{'code':'23','parma':{'ns': [8], 'nl': [30], 'time': [10]}},{'code':'16','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'101','parma':{'ns': [8], 'nl': [36], 'time': [8]}},{'code':'144','parma':{'ns': [8], 'nl': [32], 'time': [8]}},{'code':'6','parma':{'ns': [8], 'nl': [24], 'time': [9]}},{'code':'5','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'151','parma':{'ns': [8], 'nl': [32], 'time': [8]}},{'code':'11','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'66','parma':{'ns': [8], 'nl': [36], 'time': [8]}},{'code':'1044','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'19','parma':{'ns': [8], 'nl': [24], 'time': [8]}},{'code':'1038','parma':{'ns': [9], 'nl': [24], 'time': [8]}},{'code':'2','parma':{'ns': [8], 'nl': [26], 'time': [8]}},{'code':'3','parma':{'ns': [8], 'nl': [24], 'time': [9]}},{'code':'1113','parma':{'ns': [8], 'nl': [28], 'time': [12]}}]
	for code in outsample:
		# print code
		bf.setStockData(code.get('code'), False)
		bf.setStrategy("MovingMomentum", code.get('parma'))
		bStratRes, bBstRes = bf.run()
		print  bBstRes
	# bf = Bruteforce()
	# bf.setStockData("2382", True)
	# bf.setStrategy("MovingAverage")
	
	# bParam = {'snl': [40], 'hnl': [36], 'sto_n': [18], 'hns': [10], 'sto_ob': [80], 'sns': [35], 'sto_os': [30], 'sto_m': [7], 'htime': [8]}
	# bParam = {'snl': [40], 'hnl': [26], 'sto_n': [13], 'hns': [8], 'sto_ob': [80], 'sns': [35], 'sto_os': [20], 'sto_m': [3], 'htime': [9]}
	# bParam = {'ns': [8], 'nl': [32], 'time': [8]}
	# bf.setStrategy("MacdHistogram", bParam)

	