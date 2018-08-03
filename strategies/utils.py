# coding: utf-8
# autor: Eden
# date: 2018-07-31
# utils.py : use to implement sever basic function, get historical data from database, plot history data and plot the strategy's P&L.

import psycopg2
import pandas as pd
from sqlalchemy import create_engine

symbolList = []
conn = psycopg2.connect("dbname='stockdb' user='runner' password='tester'")
def getSymbolList():
	global symbolList, conn
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
			engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 
# 			stockData = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,\
# high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s'%tableName,con=engine)
			stockData = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,\
high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s where extract(epoch from (date(datetime)+ interval \'8 hour\')) > 1375171200 and \
extract(epoch from (date(datetime)+ interval \'8 hour\')) < 1380173200'%tableName,con=engine)
			return stockData

