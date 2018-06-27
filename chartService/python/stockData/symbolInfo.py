# coding: utf-8
import sys
# sys.path.insert(0, '../../grabbers/HSI')
# from yahoo_finance_HSI import get_price,get_index

class SymbolHSIInfo():

	def __init__(self, name):
		self.name = name
		self.full_name = name
		self.ticker = name
		self.description = ''
		self.type = 'stock'
		self.session = '0930-1200,1300-1600'
		self.exchange = '香港证券交易所' 
		self.listed_exchange = '香港证券交易所'
		self.timezone = 'Asia/Hong_Kong'
		self.pricescale = 2
		self.minmov = 1
		self.has_intraday = False
		self.supported_resolutions = ['1', '5', '15', '30', '60', '1D', '1W', '1M']
		self.has_daily = True
		self.has_weekly_and_monthly = True
		self.has_no_volume = False
		self.sector = ''
		self.industry = ''
		self.currency_code = 'HKD'

def getSymbolInfo(symbol):
	symbolInfo = SymbolHSIInfo(name=symbol)
	return symbolInfo

# index = get_index()
# print index
#print getSymbolInfo('0700.HK')
