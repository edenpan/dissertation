# coding: utf-8
import sys
import requests
import json
from dateutil import parser
import time
import pandas as pd
import psycopg2
import psycopg2.extras
import pandas as pd
from sqlalchemy import create_engine
import calendar；

symbolList = []
conn = psycopg2.connect("dbname='stockdb' user='runner' password='tester'")
engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 

class SymbolHistory():
	def __init__(self, symbolName, fromDate, toDate, resolution):
		#symbolName 0005
		if(symbolName.startswith("Indic#")):
			self.type = "IndicatorTick"
			self.symbolName = symbolName.split('#')[1]
			self.technical = symbolName.split('#')[2]
		else:
			self.type = "FullTick"			
			self.symbolName = symbolName
		self.fromDate = fromDate
		self.toDate = toDate
		self.webResolution = getResolution(resolution).get('p')
		#set default
		self.resolution = '1D'

		self.stripSymbolName = self.symbolName.lstrip("0")
		symbolList = getSymbolList()
		for symbol in symbolList:
			if(self.stripSymbolName == symbol[0]):
				self.tableName = symbol[1]

		self.url = 'http://127.0.0.1:8888/history/%s?resolution=%s&starttime=%s&endtime=%s'%(self.symbolName, self.webResolution, self.fromDate, self.toDate)
		# self.url = 'http://18.182.12.142:8888/history/%s?resolution=%s&starttime=%s&endtime=%s'%(self.symbolName, self.resolution, self.fromDate, self.toDate

	def getHistory(self):
		result = {}
		#to get the mac indicator
		if(self.type == 'IndicatorTick'):
			techData = []
			if( self.technical == 'MAC5'):
				macData = self.mac()
				result["s"] = "ok"
				result["type"] = self.type
				result["i1"] = macData.get('m')
				result["t"] = macData.get('t')
			if( self.technical == 'BollingerBands'):
				#return sma as i2, bl as i1, bh as i3
				bollingerData = self.bollinger()
				result["s"] = "ok"
				result["type"] = self.type
				result["i2"] = bollingerData.get('sma')
				result["i1"] = bollingerData.get('bl')
				result["i3"] = bollingerData.get('bh')
				result["t"] = bollingerData.get('t')	
			return result
		#use to request the go webserver to get the data directly.	
		# result = self.getStockDataWeb()
		#use to request the database to get the data directly.	
		result = self.getStockDataDb()
		return result

	def getData(self):
		global engine
		#目前只能查询daily数据，待后续有日间数据后再做扩展。
		#epoch时间的操作。默认存储的datetime在转为epoch是utc的，然后hk的时区是UTC+8，因为数据是最后的收盘价，
		#港股收盘时间是当地时间16：00，所以对应下来就是：extract(epoch from (date(datetime)+ interval '8 hour'))来获取当地时间的收盘价。
		data = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,high::money::numeric,low::money::numeric, adjclose::money::numeric,\
	volume,extract(epoch from (date(datetime)+ interval \'8 hour\')) as date_part from %s where extract(epoch from (date(datetime)+ interval \'8 hour\')) > %s and \
	extract(epoch from (date(datetime)+ interval \'8 hour\')) < %s'%(self.tableName,self.fromDate,self.toDate),con=engine)
		# print data
		return data		
		

	#the intraday mac strategy.
	def mac(self, window = 5):
		stockData = self.getData()
		stockData['mac' + str(window)] = stockData['adjclose'].rolling(window).mean().fillna(method='backfill')
		date1 = stockData['datetime'].values
		t = [] 
		for a in date1:
			t.append(calendar.timegm(a.timetuple()))
		m = stockData['mac5'].tolist()
		result = {'m' : m, 't': t}
		return result

	def bollinger(self, window = 20, numStd = 2):
		stockData = self.getData()
		rollingMean = stockData['adjclose'].rolling(window).mean().fillna(method='backfill')		
		rollingStd = stockData['adjclose'].rolling(window).std().fillna(method='backfill')			
		stockData['sma'] = rollingMean
		stockData['BollingerHigh'] = rollingMean + (rollingStd * numStd)
		stockData['BollingerLow'] = rollingMean - (rollingStd * numStd)

		date1 = stockData['datetime'].values
		t = [] 
		for a in date1:
			t.append(calendar.timegm(a.timetuple()))
		bh = stockData['BollingerHigh'].tolist()
		bl = stockData['BollingerLow'].tolist()
		result = {'bh' : bh, 'bl': bl, 't': t, 'sma': stockData['sma'].tolist()}
		return result


	def getStockDataDb(self):
		result = {}
		stockData = self.getData()
		if stockData is None or stockData.empty:
			result["s"] = "no_data"
		else:
			result["t"] = stockData['date_part'].tolist()
			result["v"] = stockData['volume'].tolist()
			result["c"] = stockData['close'].tolist()
			result["l"] = stockData['low'].tolist()
			result["o"] = stockData['open'].tolist()
			result["h"] = stockData['high'].tolist()
			result["type"] = self.type
			result["s"] = "ok"
		# print result	
		return result

	def getStockDataWeb(self):
			result = {}
			t =[]
			c = []
			o = []
			l = []
			h = []
			v = []
			response = requests.get(self.url)
			print self.url
			history = response.text
			historyList = json.loads(history)
			if(0 == len(historyList)):
				result["s"] = "no_data"
			else :			
				for tick in historyList:
					c.append(tick.get('adjusted_close'))
					o.append(tick.get('open'))
					h.append(tick.get('high'))
					l.append(tick.get('low'))
					v.append(tick.get('volume'))
					# print time.mktime(parser.parse(tick.get('date')))
					inttime = int(time.mktime(parser.parse(tick.get('date')).timetuple()))
					t.append(inttime)
				result["s"] = "ok"
				result["type"] = "FullTick"
				result["t"] = t
				result["v"] = v
				result["c"] = c
				result["l"] = l
				result["h"] = h
				result["o"] = o		
			# print result	
			return result		

	

# get the resolution period.
# day / hour / 30minutes / 15minutes / 5minutes / minute
def getResolution(x):
	return {
		'1':{'p':'minute'},
		'5':{'p':'5minutes'},
		'15':{'p':'15minutes'},
		'30':{'p':'30minutes'},
		'60':{'p':'hour'},
		'D':{'p':'day'},
		'1D':{'p':'day'},
	}.get(x)

#get the HSI symbol code from the postgreSQL.
def getSymbolList():
	global symbolList
	if len(symbolList) == 0:
		print "request symbolist " +  str(len(symbolList))
		conn = psycopg2.connect("dbname=stockdb user=runner")
		cur = conn.cursor()
		cur.execute("SELECT Symbol,tablename FROM config")
		symbolList = cur.fetchall()		
	print "2 symbolist " +   str(len(symbolList))
	return symbolList


# history = SymbolHistory('700', '946684800', '1529971200','1D')
# history.getHistory()
if __name__=="__main__":
	getStockDataDb('700', starttime = '1375171200', endtime = '1475173200')
