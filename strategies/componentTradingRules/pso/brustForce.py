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
			self.searchParams = strategy.parseparams(params)
		self.dimensions = len(self.searchParams)

	def run(self):
		bStratRes, bBstRes = runbackTest(self.stockData, self.strategy, **self.searchParams)
		return bStratRes, bBstRes

if __name__=="__main__":
	bf = Bruteforce()
	bf.setStockData("0005", True)
	# bf.setStrategy("MacdHistogram")
	# bf.setStrategy("MacdHistogram")
	# bf.setStrategy("MovingAverage")
	# bf.setStrategy("MovingAveConvergeDiver")
	# bf.setStrategy("BollingerBandsStrategy")
	# bf.setStrategy("StochasticOscillator")
	bf.setStrategy("MovingMomentum")

	bStratRes, bBstRes = bf.run()
	print bBstRes
	# bf.setStrategy("MacdHistogram", bBstRes[0])
	bf.setStrategy("StochasticOscillator", bBstRes[0])
	bf.setStrategy("MovingMomentum", bBstRes[0])
	# bf.setStrategy("MovingAveConvergeDiver", bBstRes[0])
	# bf.setStrategy("BollingerBandsStrategy", bBstRes[0])
	bf.setStockData("0005", False)
	bStratRes, bBstRes = bf.run()
	print bStratRes, bBstRes