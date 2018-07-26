import numpy as np
import pandas as pd
import sys
import calendar
import datetime

sys.path.append('/Users/shiqipan/code/dissertation/')
from crawler.Util import sqlUtil 

#the intraday mac strategy.
def mac(code, days):
	#get the stock data 
	symbolList = sqlUtil.getSymbolList()
	stockData = pd.DataFrame()
	for symbol in symbolList:
		if(code == symbol[0]):
			tableName = symbol[1]
			print tableName
			stockData = sqlUtil.getDaliyData(tableName)
			print stockData.head()
	stockData['mac' + str(days)] = stockData['adjclose'].rolling(days).mean().fillna(method='backfill')
	date1 = stockData['datetime'].values
	t = [] 
	for a in date1:
		t.append(calendar.timegm(a.timetuple()))
	print t
	m = stockData['mac' + str(days)].tolist()
	result = {'m' : m, 't': t}
	print result
	return result

if __name__=="__main__":
	mac("5", 5)	
