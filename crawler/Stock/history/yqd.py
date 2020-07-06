# -*- coding: utf-8 -*-
"""
Reference:https://github.com/c0redumb/yahoo_quote_download/blob/master/yahoo_quote_download/yqd.py
Created on Thu May 18 22:58:12 2017
@author: c0redumb

Changing storing data into stockDB
@Eden
"""


# To make print working for Python2/3
from __future__ import print_function

# Use six to import urllib so it is working for Python2/3
from six.moves import urllib
# If you don't want to use six, please comment out the line above
# and use the line below instead (for Python3 only).
#import urllib.request, urllib.parse, urllib.error

import time
import pandas as pd
from time import sleep

'''
Starting on May 2017, Yahoo financial has terminated its service on
the well used EOD data download without warning. This is confirmed
by Yahoo employee in forum posts.
Yahoo financial EOD data, however, still works on Yahoo financial pages.
These download links uses a "crumb" for authentication with a cookie "B".
This code is provided to obtain such matching cookie and crumb.
'''

# Build the cookie handler
cookier = urllib.request.HTTPCookieProcessor()
opener = urllib.request.build_opener(cookier)
urllib.request.install_opener(opener)

# Cookie and corresponding crumb
_cookie = None
_crumb = None

# Headers to fake a user agent
_headers={
	'User-Agent': 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11'
}

def _get_cookie_crumb():
	'''
	This function perform a query and extract the matching cookie and crumb.
	'''

	# Perform a Yahoo financial lookup on SP500
	req = urllib.request.Request('https://finance.yahoo.com/quote/^GSPC', headers=_headers)
	f = urllib.request.urlopen(req)
	alines = f.read().decode('utf-8')

	# Extract the crumb from the response
	global _crumb
	cs = alines.find('CrumbStore')
	cr = alines.find('crumb', cs + 10)
	cl = alines.find(':', cr + 5)
	q1 = alines.find('"', cl + 1)
	q2 = alines.find('"', q1 + 1)
	crumb = alines[q1 + 1:q2]
	_crumb = crumb

	# Extract the cookie from cookiejar
	global cookier, _cookie
	for c in cookier.cookiejar:
		if c.domain != '.yahoo.com':
			continue
		if c.name != 'B':
			continue
		_cookie = c.value

	# Print the cookie and crumb
	print('Cookie:', _cookie)
	print('Crumb:', _crumb)

def load_yahoo_quote(ticker, begindate, enddate, info = 'quote', format_output = 'list'):
	'''
	This function load the corresponding history/divident/split from Yahoo.
	'''
	# Check to make sure that the cookie and crumb has been loaded
	global _cookie, _crumb
	if _cookie == None or _crumb == None:
		_get_cookie_crumb()

	# Prepare the parameters and the URL
	tb = time.mktime((int(begindate[0:4]), int(begindate[4:6]), int(begindate[6:8]), 4, 0, 0, 0, 0, 0))
	te = time.mktime((int(enddate[0:4]), int(enddate[4:6]), int(enddate[6:8]), 18, 0, 0, 0, 0, 0))
	print( tb, te)

	param = dict()
	param['period1'] = int(tb)
	param['period2'] = int(te)
	param['interval'] = '1d'
	if info == 'quote':
		param['events'] = 'history'
	elif info == 'dividend':
		param['events'] = 'div'
	elif info == 'split':
		param['events'] = 'split'
	param['crumb'] = _crumb
	
	params = urllib.parse.urlencode(param)
	url = 'https://query1.finance.yahoo.com/v7/finance/download/{}?{}'.format(ticker, params)
	#print(url)
	req = urllib.request.Request(url, headers=_headers)
	print("req rest:" + str(req))
	# Perform the query
	# There is no need to enter the cookie here, as it is automatically handled by opener
	f = urllib.request.urlopen(req)
	alines = f.read()
	print(alines)
	if format_output == 'list':
		return alines.split('\n')

	if format_output == 'dataframe':
		nested_alines = [line.split(',') for line in alines.split('\n')[1:]]
		print(nested_alines[:-1] )
		#just use the db's column header.

		dbCols = ['datetime' ,'open' ,'high' ,'low' ,'close' ,'adjclose' ,'volume']
		adf = pd.DataFrame.from_records(nested_alines[:-1], columns=dbCols)
		return adf


def load_quote(ticker):
	print('===', ticker, '===')
	print(load_yahoo_quote(ticker, '20100701', '20180712', format_output = 'dataframe'))
	#print(load_yahoo_quote(ticker, '20170515', '20170517', 'dividend'))
	#print(load_yahoo_quote(ticker, '20170515', '20170517', 'split'))

def testDB():
	import sys
	sys.path.append('/Users/shiqipan/code/dissertation/')
	from crawler.Util import sqlUtil 
	index = sqlUtil.getSymbolList()
	for code in index:
		symbolCode = str(code[0]).zfill(4) + '.HK'
		tableName = code[1]
		print('===', tableName, '===')
		history = load_yahoo_quote(symbolCode, '20180712', '20190327', format_output = 'dataframe')
		sqlUtil.insertPd(tableName, history)
		sleep(1)

#insert history data into postgreSql
def test():
	import sys
	sys.path.append('/Users/shiqipan/code/dissertation/')
	from crawler.Util import sqlUtil 
	index = sqlUtil.getSymbolList()
	# tableList = [['5' ,'hsbc_holdings'],['11' ,'hang_seng_bank'],['23' ,'bank_of_e_asia'],['388' ,'hkex'],['939' ,'ccb'],['1299' ,'aia'],['1398' ,'icbc'],['2318' ,'ping_an'],['2388' ,'boc_hong_kong'],['2628' ,'china_life'],['3328' ,'bankcomm'],['3988' ,'bank_of_china'],['2' ,'clp_holdings'],['3' ,'hk_china_gas'],['6' ,'power_assets'],['836' ,'china_res_power'],['1038' ,'cki_holdings'],['83' ,'sino_land']]
	# tableList = [['5' ,'hsbc_holdings']]
	tableList = [['%5EHS' ,'hsi_index']]

	for table in tableList:
		symbolCode = str(table[0]).zfill(4) + '.HK'
		tableName = table[1]
		print('===', tableName, '===')
		# history = load_yahoo_quote(symbolCode, '20070701', '20180729', format_output = 'dataframe')
		history = load_yahoo_quote(symbolCode, '20170701', '20180729', format_output = 'dataframe')
		# sqlUtil.insertPd(tableName, history)
		sleep(1)

if __name__=="__main__":
	test()
# load_quote("0700.hk")
#testDB()	