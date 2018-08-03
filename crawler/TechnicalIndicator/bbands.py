# coding: utf-8
# Calculate the Bollinger-bands by using the daily data.
import numpy as np
import pandas as pd
import sys
import calendar
import datetime

sys.path.append('/Users/shiqipan/code/dissertation/')
from crawler.Util import sqlUtil 

#the Bollinger-bands indicator
def bbands(code, windows):
	#get the stock data 
	symbolList = sqlUtil.getSymbolList()
	stockData = pd.DataFrame()
	for symbol in symbolList:
		if(code == symbol[0]):
			tableName = symbol[1]
			#print tableName
			stockData = sqlUtil.getDaliyData(tableName)
			#print stockData.head()
	stockData['rm' + str(windows)] = stockData['adjclose'].rolling(windows).mean().fillna(method='backfill')
	stockData['rstd'+ str(windows)]  = stockData['adjclose'].rolling(windows).std().fillna(method='backfill')
	stockData['upper'] = stockData['rm' + str(windows)] + stockData['rstd'+ str(windows)] 
	stockData['lower'] = stockData['rm' + str(windows)] - stockData['rstd'+ str(windows)] 
	date1 = stockData['datetime'].values
	t = [] 
	for a in date1:
		t.append(calendar.timegm(a.timetuple()))
	print t
	m = stockData['rm' + str(windows)].tolist()
	result = {'m' : m, 'u': stockData['upper'].tolist(), 'l': stockData['lower'].tolist()}
	print result
	return result

if __name__=="__main__":
	bbands("5", 20)	


