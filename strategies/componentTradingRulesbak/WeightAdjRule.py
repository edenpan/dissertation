# coding: utf-8
# autor:Eden
# date:2018-08-06
#
# WeightAdjRule.py : adjust the component rules based on the past ms peroids performance 
# Input: Currend Day:d, Rule Weights: wt  --- list of component rule 
# Output: Updated Rule Weights: wt
# 
import bb
import sys
sys.path.append('../')
import utils
import pandas as pd

startDate = '20130701'
ms = 200
testDate = '20160701'

#param list for every rule to get the profit result 
bb_n = [10]
bb_k = [1.5]
# bb_n = [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 75, 80, 90, 100, 125, 150, 175, 200, 250]
# bb_k = [1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5]
macd_nl = [15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
macd_ns = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200]
ma_nl = [15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250]
ma_ns = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200]
rsi_n = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
rsi_ob = [80, 75, 70]
rsi_os = [20, 25, 30]


def InitalWt(totalNum):
	weight = []
	for i in range(totalNum):
		weight.append(1.0/totalNum)
	return weight

def WeightAdjRule(CurrentDate, code, ms = 200):
	weight = InitalWt(220)
	# print weight
	stockData = utils.getStockData(code)
	testStockData = stockData[:ms]
	print testStockData
	profit = []
	profitNum = 0
	# for i in range(len(weight)):
	for n in bb_n:
		for k in bb_k:
			res = bb.BollingerBands(testStockData, bb_n, bb_k)
			invest = res["score" + str(n) + '_' +  str(k)]
			print invest
			capNum = 10000.0
			state = False
			print invest
			for row in res.itertuples():
				print row

				



WeightAdjRule(testDate, '5')
