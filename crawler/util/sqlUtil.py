import psycopg2
import psycopg2.extras
import pandas as pd
from sqlalchemy import create_engine

symbolList = []
conn = psycopg2.connect("dbname='stockdb' user='runner' password='tester'")
engine = create_engine('postgresql://runner:tester@localhost/stockdb', echo=False) 

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
	
def insert1():
	print getSymbolList()
	global conn
	cur = conn.cursor()
	l = []
	l.append("'2015-06-30',17599.960938,17714.660156,17576.500000,17619.509766,17619.509766,126460000")
	l.append("'2015-07-01',17638.119141,17801.830078,17638.119141,17757.910156,17757.910156,87010000")
	l.append("'2015-07-02',17763.320313,17825.490234,17687.519531,17730.109375,17730.109375,83080000")
	insert = "INSERT INTO aac_tech(Datetime, Open, High, Low, Close, AdjClose, Volume) VALUES %s"
	print str(l)
	i = 0;
	insertList = "["
	for i in range(len(l) - 1):
		insertList += "(" + l[i] +"),"
	insertList += "(" + l[len(l)-1] +")]"	
	print insertList	
	psycopg2.extras.execute_values(cur, "INSERT INTO aac_tech(Datetime, Open, High, Low , Close, AdjClose , Volume) VALUES %s", [('2015-06-30',17599.960938,17714.660156,17576.500000,17619.509766,17619.509766,126460000),('2015-07-01',17638.119141,17801.830078,17638.119141,17757.910156,17757.910156,87010000),('2015-07-02',17763.320313,17825.490234,17687.519531,17730.109375,17730.109375,83080000)])
	conn.commit()


def insert2(tableName, recordlist):
	global conn
	cur = conn.cursor()
	print tableName,recordlist
	insertList = "INSERT INTO %s(Datetime, Open, High, Low, Close, AdjClose, Volume) VALUES "%tableName
	print insertList
	for i in range(len(recordlist)):
		#if the return is null,just return the index.
		if 'null' == recordlist[i].split(',')[0]:
			print tableName
			print "*" * 20
			print i
			return 
		print recordlist[i]
		meta = recordlist[i].split(',')
		meta[0] = "\'" + meta[0] + "\'"				
		recordlist=" ".join(meta)	
		insertList += "(" + recordlist +"),"
	insertList += "(" + recordlist[len(recordlist)-1] +");"	
	print insertList
	cur.execute(insertList)
	conn.commit()


def insertPd(tableName, pdRecord):
	global engine, conn
	insertList = "INSERT INTO %s(datetime, open, high, low, close, adjclose, volume) VALUES "%tableName
	pdRecord['datetime'] = '\'' + pdRecord['datetime'] + '\''
	# print pdRecord
	try:
		pdRecord.to_sql(name=tableName, con=engine,schema = 'public', if_exists='append',index=False, chunksize=10000)
		# sql = "select count(*) from %s;"%tableName
		# df = pd.read_sql(sql,con)
		conn.commit()
	except psycopg2.DatabaseError as e:
		print('Error %s' % e)
		sys.exit(1)
	finally:
		if conn:
			conn.close()		
	

def testList():
	global conn
	cur = conn.cursor()
	l = []
	l.append("'2015-06-30',17599.960938,17714.660156,17576.500000,17619.509766,17619.509766,126460000")
	l.append("'2015-07-01',17638.119141,17801.830078,17638.119141,17757.910156,17757.910156,87010000")
	l.append("'2015-07-02',17763.320313,17825.490234,17687.519531,17730.109375,17730.109375,83080000")
	insertList = "INSERT INTO aac_tech(Datetime, Open, High, Low, Close, AdjClose, Volume) VALUES "
	print(str(l))
	i = 0;
	# insertList = "["
	for i in range(len(l) - 1):
		insertList += "(" + l[i] +"),"
	insertList += "(" + l[len(l)-1] +");"	
	# print insertList
	cur.execute(insertList)
	conn.commit()

def testPd():
	global conn
	cur = conn.cursor()
	l = []
	l.append("2015-06-30,17599.960938,17714.660156,17576.500000,17619.509766,17619.509766,126460000")
	l.append("2015-07-01,17638.119141,17801.830078,17638.119141,17757.910156,17757.910156,87010000")
	l.append("2015-07-02,17763.320313,17825.490234,17687.519531,17730.109375,17730.109375,83080000")
	d = []
	for a in l:
		d.append(a.split(','))
	# print d
	df = pd.DataFrame(data=d, columns = ['datetime' ,'open' ,'high' ,'low' ,'close' ,'adjclose' ,'volume'])
	# print df 
	insertPd('aac_tech', df)

def getDaliyData(tableName):
	global engine
	data = pd.read_sql_query('select datetime,open::money::numeric,close::money::numeric,high::money::numeric,low::money::numeric, adjclose::money::numeric, volume from %s'%tableName,con=engine)
	return data



if __name__=="__main__":
	testPd()	
	

#insert2("AAC_Tech", [])

