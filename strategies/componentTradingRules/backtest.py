# coding: utf-8
# autor:Eden
# date:2018-07-31
# backtest.py : use to run the backtesting framework
#				The params need to set : oriCap = 10000.00, stockData
# return: roi(roi = (capNow-oriCap)/oriCap)
#The problem is how to set this as an interface that the pso or other's only need to call this function, rather then
# to call the real implement strategy?
import bb
import sys
sys.path.append('../')
import utils
from datetime import timedelta  
import pandas as pd

def filtZero(df, key, value):
	return df[df[key] != value]

def runbackTest(code, oriCap = 10000.00):
	stockData = utils.getStockData(code)
	result, n = bb.BollingerBands(stockData)
	strategyResList 
	i = 0
	while i < n:
		cap = oriCap
		execList = []
		state = False
		stockNum = 0.0
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
				print cap
				stockNum = 0.0
				state = False
				execList.append((date,"sell",cap))
		if len(execList) > 0:
			# At the end, execute the sell if held any stock so that can calculate the roi		
			if state:
				cap = stockData.iloc[-1].adjclose.values[0] * stockNum
			print "cap" + str(cap)
			roi = (cap-oriCap)/oriCap
			print str(result.columns[i]) +" roi is : " + str(roi)
			print "execute list " + str(execList)
		
		i = i + 1
	# for row in stockData.itertuples():
	# 	print row

if __name__=="__main__":
	pd.DataFrame.mask = filtZero
	runbackTest('0005')



