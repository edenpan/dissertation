#Transaction logic
#		  = buy,	if (SMAt1 > SMAt2) and (SMAt3 > SMAt4)
#  signal = sell ,  if (SMAt5 < SMAt6) and (SMAt7 < SMAt8)
#		  = hold, otherwise 
#get the HSI symbol code from the postgreSQL.
import pandas as pd
import psycopg2
import psycopg2.extras
import pandas as pd
from sqlalchemy import create_engine
import calendar
import matplotlib.pyplot as pp

symbolList = []
def getSymbolList():
	global symbolList
	conn = psycopg2.connect("dbname='stockdb' user='runner' password='tester'")
	if len(symbolList) == 0:
		conn = psycopg2.connect("dbname=stockdb user=runner")
		cur = conn.cursor()
		cur.execute("SELECT Symbol,tablename FROM config")
		symbolList = cur.fetchall()		
	return symbolList

def getStockData(code):
	code = code.lstrip("0")
	symbolList = getSymbolList()
	stockData = pd.DataFrame()
	for symbol in symbolList:
		if(code == symbol[0]):
			tableName = symbol[1]
			stockData = getDaliyData(tableName)
			return stockData

def getDaliyData(tableName):
	engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 
	data = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s'%tableName,con=engine)
	return data	

def smaCross(intervelList):
	# state False - holding capital; True - holding stock
	capNum = 10000.0;
	stockNum = 0.0;
	state = False
	stockData = getStockData('5')
	i = 1
	while i <= len(intervelList):
		intervel = intervelList[i-1]
		stockData['sma' + str(i)] = stockData['adjclose'].rolling(intervel).mean().fillna(method='backfill')
		i = i + 1
	# plotdata = pd.DataFrame()	
	sell = {"X" : [], "Y": []}
	buy = {"X" : [], "Y": []}
	for row in stockData[200: ].itertuples():
		adjRatio = row.adjclose/row.close
		# data = pd.DataFrame({"close": adjRatio * row.close, "high": adjRatio * row.high, "low": adjRatio * row.high, "open": adjRatio * row.open, "sma1":row.sma1, "sma2": row.sma2,"sma3":row.sma3, "sma4": row.sma4,"sma5":row.sma5, "sma6": row.sma6,"sma7":row.sma7, "sma8": row.sma8 })
		# plotdata = plotdata.append({"datetime": row.datetime, "close": (adjRatio * row.close), "high": (adjRatio * row.high), "low": adjRatio * row.high, "open": adjRatio * row.open, "sma1":row.sma1, "sma2": row.sma2,"sma3":row.sma3, "sma4": row.sma4,"sma5":row.sma5, "sma6": row.sma6,"sma7":row.sma7, "sma8": row.sma8 }, ignore_index=True)
	
		if(row.sma1 > row.sma2) and (row.sma3 > row.sma4) and (state == False):
			StockNum = capNum/(adjRatio * (row.high + row.low)/2)
			state = True
			capNum = 0.0
			buy["X"].append(row.datetime)
			buy["Y"].append((adjRatio* (row.high + row.low)/2))
			# print "buy " + str(StockNum) + " at " + str(row.datetime) + "with price:" + str((adjRatio* (row.high + row.low)/2))

		if (row.sma5 < row.sma6) and (row.sma7 < row.sma8) and (state == True):
			# print "sell " + str(StockNum) + " at " + str(row.datetime) + "with price:" + str((adjRatio * (row.high + row.low)/2))
			capNum = StockNum*(adjRatio * (row.high+row.low)/2.0)
			sell["X"].append(row.datetime)
			sell["Y"].append((adjRatio* (row.high + row.low)/2))
			StockNum = 0.0
			state = False
	# print "StockNum:" + str(stockData.tail(1).high + stockData.tail(1).low)

	if(state):
		capNum = StockNum*((stockData.tail(1).high.values[0] + stockData.tail(1).low.values[0])/2)
	# print "final capital: " + str(capNum)
	roi = (capNum-10000.0)/10000.0
	# print "roi: " + str(roi)	
	return roi
	# plotPrice2(stockData, plotdata)

#only simple plot 
def plotPrice1(stockData):
	stockData = stockData.sort_values(by='datetime')
	stockData.set_index('datetime',inplace=True)	
	stockData['close'].plot(figsize=(16, 12))
	pp.sellhow()
#plot candlestick and the sma and the sell point and buy point.
def plotPrice2(stockData, plotdata):
	import sys
	sys.path.append('/Users/shiqipan/code/python/playground')
	from candlestickChart import pandas_candlestick_ohlc
	stockData = stockData.sort_values(by='datetime')
	plotdata.set_index('datetime',inplace=True)	
	stockData.set_index('datetime',inplace=True)	
	# print plotdata.head()
	pandas_candlestick_ohlc(plotdata, otherseries = ['sma1', 'sma2','sma3', 'sma4','sma5', 'sma6','sma7', 'sma8'],buy= buy, sell =sell)

if __name__=="__main__":
	smaCross([5, 120, 60, 200, 5, 120, 60, 200])		

