# coding: utf-8
# autor: Eden
# date: 2018-07-31
# utils.py : use to implement sever basic function, get historical data from database, plot history data and plot the strategy's P&L.
# add log config
import psycopg2
import pandas as pd
from sqlalchemy import create_engine
import datetime

symbolList = {}
# conn = psycopg2.connect("dbname='stockdb' user='runner' password='tester'")
conn =""
def getSymbolList():
	global symbolList, conn
	if len(symbolList) == 0:
		conn = psycopg2.connect("dbname=stockdb user=runner")
		cur = conn.cursor()
		cur.execute("SELECT Symbol,tablename FROM config")
		tempList = cur.fetchall()		
		for symbol in tempList:
			symbolList[symbol[0]] = symbol[1]
	return symbolList

def getStockData(code):
	code = code.lstrip("0")
	symbolList = getSymbolList()
	stockData = pd.DataFrame()
	if(None != symbolList.get(code)):
		tableName = symbolList.get(code)
		engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 
# 			stockData = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,\
# high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s'%tableName,con=engine)
		stockData = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,\
high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s where extract(epoch from (date(datetime)+ interval \'8 hour\')) > 1375171200 and \
extract(epoch from (date(datetime)+ interval \'8 hour\')) < 1380173200'%tableName,con=engine)
		return stockData

def getStockDataTrain(code, isTrain):
	code = code.lstrip("0")
	symbolList = getSymbolList()
	stockData = pd.DataFrame()
	if(None != symbolList.get(code)):
		tableName = symbolList.get(code)
		engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 
		if isTrain:
			#get data from 2013/07/13 to 2016/12/12
			stockData = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,\
high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s where extract(epoch from (date(datetime)+ interval \'8 hour\')) > 1375171200 and \
extract(epoch from (date(datetime)+ interval \'8 hour\')) < 1481558480'%tableName,con=engine)
		if (not isTrain):
			stockData = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,\
high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s where \
extract(epoch from (date(datetime)+ interval \'8 hour\')) > 1481558480'%tableName,con=engine)	
		return stockData

#the hole range in the database is :2013-07-13 to  2018-07-12
# The format of time input: 2018-07-12
# getStockDataWithTime('0005', '2013-07-15', '2018-07-12')
def getStockDataWithTime(code, startTime, endTime):
	code = code.lstrip("0")
	symbolList = getSymbolList()
	stockData = pd.DataFrame()
	start = transferDate(startTime)
	end = transferDate(endTime)
	if(None != symbolList.get(code)):
		tableName = symbolList.get(code)
		engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 
		#get data from 2013/07/13 to 2016/12/12
		querySql = "select datetime,open::money::numeric,close::money::numeric,\
high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from {0} where extract(epoch from (date(datetime)+ interval \'1 hour\')) > {1} and \
extract(epoch from (date(datetime)- interval \'1 hour\')) < {2}"
		querySql = querySql.format(tableName,start, end)
		stockData = pd.read_sql_query(querySql,con=engine)			
		return stockData

def unix_time_millis(dt):
	epoch = datetime.datetime.utcfromtimestamp(0)
	return (dt - epoch).total_seconds()

def getStockDataWithTimeFromCSV(code, startTime, endTime):
	code = code.zfill(4)+".HK.csv"
	path = "/home/edenpan/code/python/myInterest/financial/hkStockData/" + code
	stockData = pd.read_csv(path, infer_datetime_format=True, header=0,
							names=['datetime', 'open', 'high', 'low', 'close', 'adjclose', 'volume'])
	print(stockData)
	startData = stockData[stockData['datetime'] >= startTime]
	stockData = startData[startData['datetime'] <= endTime]
	print(stockData)
	return stockData

def transferDate(strDate):
	date = strDate.split('-')
	dt = datetime.datetime(int(date[0]), int(date[1]), int(date[2]))
	return int(unix_time_millis(dt))




def frange(x, y, jump):
	k = range(int((y-x)/jump))
	interval = jump
	flist = []
	for i in k:
		flist.append(i*interval + x)
	return flist	






