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
import calendar
symbolList = []
conn = psycopg2.connect("dbname='stockdb' user='runner' password='tester'")
engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 

class SymbolHistory():
	def __init__(self, symbolName, fromDate, toDate, resolution):
		self.symbolName = symbolName
		self.fromDate = fromDate
		self.toDate = toDate
		self.resolution = getResolution(resolution).get('p')
		# self.url = 'http://127.0.0.1:8888/history/%s?resolution=%s&starttime=%s&endtime=%s'%(self.symbolName, self.resolution, self.fromDate, self.toDate)
		self.url = 'http://18.182.12.142:8888/history/%s?resolution=%s&starttime=%s&endtime=%s'%(self.symbolName, self.resolution, self.fromDate, self.toDate)
	
	def getHistory(self):
		result = {}
		t =[]
		c = []
		o = []
		l = []
		h = []
		v = []
		#to get the mac indicator
		if(self.symbolName.startswith("Indic#")):
			code = self.symbolName.split('#')[1]
			technical = self.symbolName.split('#')[2]
			techData = []
			if( technical == 'MAC5'):
				# inttime = int(time.mktime(parser.parse(tick.get('date')).timetuple()))
				# t.append(inttime)
				macData = mac(code)
				result["s"] = "ok"
				result["c"] = macData.get('m')
				result["t"] = macData.get('t')

			return result
		
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
			result["t"] = t
			result["v"] = v
			result["c"] = c
			result["l"] = l
			result["h"] = h
			result["o"] = o
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

def getDaliyData(tableName):
	global engine
	data = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s'%tableName,con=engine)
	return data	


#the intraday mac strategy.
def mac(code):
	print code
	code = code.lstrip("0")
	print code
	#get the stock data 
	symbolList = getSymbolList()
	stockData = pd.DataFrame()
	for symbol in symbolList:
		if(code == symbol[0]):
			tableName = symbol[1]
			print tableName
			stockData = getDaliyData(tableName)
			print stockData.head()
	stockData['mac5'] = stockData['adjclose'].rolling(5).mean().fillna(method='backfill')
	date1 = stockData['datetime'].values
	t = [] 
	for a in date1:
		t.append(calendar.timegm(a.timetuple()))
	m = stockData['mac5'].tolist()
	result = {'m' : m, 't': t}
	return result


# history = SymbolHistory('700', '946684800', '1529971200','1D')
# history.getHistory()

