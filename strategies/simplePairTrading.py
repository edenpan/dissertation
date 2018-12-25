# coding: utf-8
# autor:Eden
# date:2018-11-06
# Implement a simple pair trading strategie from :
# https://medium.com/auquan/pairs-trading-data-science-7dbedafcfe5a
import sys
sys.path.append('../')
import utils
import itertools
import pandas as pd
import numpy as np
import math
from statsmodels.tsa.stattools import coint
# import matplotlib.pyplot as plt

class SimplePairTrading:
	def __init__(self):
		self.strategyName = "SimplePairTrading"
		self.stockList = utils.getSymbolList()
		self.getAllStockData()

	def getAllStockData(self):
		start = '2013-07-15'
		end = '2018-07-12'
		stockList = self.stockList.viewkeys()
		self.adjClose = pd.DataFrame()
		for stock in stockList:
			stockData = utils.getStockDataWithTime(stock, start, end)
			self.adjClose[self.stockList[stock]] = pd.Series(stockData['adjclose'].values, index = stockData['datetime'])
		# print self.adjClose

	def find_cointegrated_pairs(self):
		n = self.adjClose.shape[1]
		score_matrix = np.zeros((n, n))
		pvalue_matrix = np.ones((n, n))
		keys = self.adjClose.keys()
		pairs = []
		for i in range(n):
			for j in range(i+1, n):
				S1 = self.adjClose[keys[i]]
				S2 = self.adjClose[keys[j]]
				tempS1 = S1.fillna(value = 0)			
				tempS2 = S2.fillna(value = 0)
				result = coint(tempS1, tempS2)
				score = result[0]
				pvalue = result[1]
				score_matrix[i, j] = score
				pvalue_matrix[i, j] = pvalue
				if pvalue < 0.02:
					pairs.append((keys[i], keys[j]))
		return score_matrix, pvalue_matrix, pairs	

	def findPair(self):
		# scores, pvalues, self.pairs = self.find_cointegrated_pairs()
		self.pairs = [('china_unicom', 'china_res_power'), ('china_unicom', 'hang_lung_ppt'), ('sino_land', 'wh_group'), ('sino_land', 'aac_tech'), ('sino_land', 'henderson_land'), ('bank_of_e_asia', 'ccb'), ('bank_of_e_asia', 'aac_tech'), ('bank_of_e_asia', 'new_world_dev'), ('bank_of_e_asia', 'shk_ppt'), ('wh_group', 'henderson_land'), ('hk_china_gas', 'aia'), ('power_assets', 'china_mobile'), ('boc_hong_kong', 'new_world_dev'), ('country_garden', 'sunny_optical'), ('icbc', 'new_world_dev'), ('shk_ppt', 'bank_of_china'), ('china_overseas', 'aia'), ('china_overseas', 'link_reit'), ('aia', 'china_res_land')]
		# import seaborn 
		# m = [0,0.2,0.4,0.6,0.8,1]
		# seaborn.heatmap(pvalues, xticklabels=self.stockList.viewvalues(), yticklabels=self.stockList.viewvalues(), cmap='RdYlGn_r', mask = (pvalues >= 0.98))
		# plt.show()
		# print scores, pvalues, self.pairs

	def testAllPair(self):
		for pair in self.pairs:
			S1 = self.adjClose[pair[0]][:863]
			S2 = self.adjClose[pair[1]][:863]
			print pair
			print self.trade(S1, S2, 60, 5)


	# Trade using a simple strategy
	def trade(self, S1, S2, window1, window2):
		# If window length is 0, algorithm doesn't make sense, so exit
		if (window1 == 0) or (window2 == 0):
			return 0
		# Compute rolling mean and rolling standard deviation
		ratios = S1/S2
		ma1 = ratios.rolling(window=window1,center=False).mean()
		ma2 = ratios.rolling(window=window2,center=False).mean()
		std = ratios.rolling(window=window2,center=False).std()
		zscore = (ma1 - ma2)/std
		# Simulate trading
		# Start with no money and no positions
		money = 0
		countS1 = 0
		countS2 = 0
		for i in range(len(ratios)):
			# Sell short if the z-score is > 1
			if zscore[i] > 1:
				money += S1[i] - S2[i] * ratios[i]
				countS1 -= 1
				countS2 += ratios[i]
				# print('Selling Ratio %s %s %s %s'%(money, ratios[i], countS1,countS2))
			# Buy long if the z-score is < 1
			elif zscore[i] < -1:
				money -= S1[i] - S2[i] * ratios[i]
				countS1 += 1
				countS2 -= ratios[i]
				# print('Buying Ratio %s %s %s %s'%(money,ratios[i], countS1,countS2))
			# Clear positions if the z-score between -.5 and .5
			elif abs(zscore[i]) < 0.75:
				money += S1[i] * countS1 + S2[i] * countS2
				countS1 = 0
				countS2 = 0
				# print('Exit pos %s %s %s %s'%(money,ratios[i], countS1,countS2))
		return money

		
# S1 = variables['pairTrading'].adjClose['china_unicom'][863:]
# S2 = variables['pairTrading'].adjClose['china_res_power'][863:]
# trade(data['ADBE'].iloc[:1763], data['MSFT'].iloc[:1763], 60, 5)
if __name__=="__main__":
	# stockDataTrain = utils.getStockDataTrain("0005", True)
	pairTrading = SimplePairTrading()
	pairTrading.findPair()
	print pairTrading.pairs
	pairTrading.testAllPair()
	