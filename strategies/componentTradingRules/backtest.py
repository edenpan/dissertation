# coding: utf-8
# autor:Eden
# date:2018-07-31
# backtest.py : use to run the backtesting framework
#				The params need to set : oriCap = 10000.00, stockData
# return: roi(roi = (capNow-oriCap)/oriCap)
#The problem is how to set this as an interface that the pso or other's only need to call this function, rather then
# to call the real implement strategy?
from  bb import BollingerBands
from  bb import defaultParam as bbDefualtParams
from  bb import parseparams as bbparseparams
from  ma import ma
import sys
sys.path.append('../')
import utils
from datetime import timedelta  
import pandas as pd

def filtZero(df, key, value):
	return df[df[key] != value]

def runbackTest(code, strategyName, isTrain, oriCap = 10000.00, **kwargs):
	pd.DataFrame.mask = filtZero
	stockData = utils.getStockDataTrain(code, isTrain)

	result, n = globals()[strategyName](stockData, **kwargs)
	bestRoi = -99999.99
	bestParam = ''
	strategyResList = []
	i = 0
	while i < n:
		cap = oriCap
		execList = []
		state = False
		stockNum = 0.0
		bestParam = result.columns[i]
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
			bestRoi = roi
			bestParam = result.columns[i]
		strategyResList.append({"BollingerBands_" + str(result.columns[i]) : (roi, execList)})
		
		i = i + 1
	bestRes = (bestParam, bestRoi)
	return strategyResList, bestRes

if __name__=="__main__":
	params = globals()["bbDefualtParams"]()
	print params
	# params['stockData'] = stockData
	bStratRes, bBstRes = runbackTest('0005', "BollingerBands", True, **params )

	bParam = globals()["bbparseparams"](bBstRes[0])
	print bParam
	runbackTest('0005', "BollingerBands", False, **bParam)
	# runbackTest('0005', "BollingerBands", False, **params)



