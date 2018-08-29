# coding: utf-8
# autor:Eden
# date:2018-07-31
# backtest.py : use to run the backtesting framework
#				The params need to set : oriCap = 10000.00, stockData
# return: roi(roi = (capNow-oriCap)/oriCap)
#The problem is how to set this as an interface that the pso or other's only need to call this function, rather then
# to call the real implement strategy?
import importlib
import sys
sys.path.append('../')
import utils
from datetime import timedelta  
import pandas as pd

def filtZero(df, key, value):
	return df[df[key] != value]

def runbackTest(stockData, strategy, oriCap = 10000.00, **kwargs):
	pd.DataFrame.mask = filtZero
	result, n = strategy.run(stockData, **kwargs)
	bestRoi = -99999.99
	bestParam = ""
	strategyResList = []
	i = 0
	while i < n:
		cap = oriCap
		execList = []
		state = False
		stockNum = 0.0
		# bestParam = result.columns[i]
		effectRows = result.mask(result.columns[i], 0.0)
		for date, signal in effectRows[result.columns[i]].iteritems():
			#if the singal is buy(>0) and the state is False that no hold any stock,will excute buy
			#the execute price is just the adjclose price that day's singal.
			if (signal > 0) and (state == False):
				stockNum = cap/stockData.loc[stockData["datetime"] == date]["adjclose"].values[0]
				state = True
				execList.append((date,"buy",stockNum))
			#if the singal is Sell(<0) and the state is True that held stocks,will excute sell				
			if signal < 0 and state:
				cap = stockData.loc[stockData["datetime"] == date]["adjclose"].values[0]* stockNum
				stockNum = 0.0
				state = False
				execList.append((date,"sell",cap))
			
		if state:
			cap = stockData.iloc[-1].adjclose * stockNum
		roi = (cap-oriCap)/oriCap
		if bestRoi < roi:
			bestParam = result.columns[i]
			bestRoi = roi
		strategyResList.append({strategy.strategyName +"-" + str(result.columns[i]) : (roi, execList)})
		i = i + 1
	# print "runtimes: " + str(i)		
	bestRes = (bestParam, bestRoi)
	return strategyResList, bestRes



if __name__=="__main__":
	module = importlib.import_module("BollingerBandsStrategy")
	class_ = getattr(module, "BollingerBandsStrategy")
	strategy = class_()

	params = strategy.defaultParam()
	print params
	# params['stockData'] = stockData
	isTrain = True
	stockDataTrain = utils.getStockDataTrain("0005", isTrain)
	bStratRes, bBstRes = runbackTest(stockDataTrain, strategy, **params )
	print bStratRes, bBstRes
	bParam = strategy.parseparams(bBstRes[0])
	print bParam
	stockDataTest = utils.getStockDataTrain("0005", not isTrain)
	print runbackTest(stockDataTest, strategy, **bParam)
	# runbackTest('0005', "BollingerBands", False, **params)



