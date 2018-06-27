# coding: utf-8
import sys
sys.path.insert(0, '../../grabbers/HSI')
from yahoo_finance_HSI import get_price,get_index

class symbolHistory():
	def __init__(self):
		self.s = 'ok'



def getHistory(symbolName, from, to, resolution):
	i = 60
	p = '1M'


def resolution(x):
	return {
		'5':{'i':5 * 60,'p':'1M'},
		'15':{'i':15 * 60,'p':'1M'},
		'30':{'i':30 * 60, 'p':'1M'},
		'1D':{'i':24 * 60 * 60, 'p':'3M'},
		'1W':{'i': 7 * 24 * 60 * 60,'p':'1y'},
		'1M':{'i': 4 * 7 * 24 * 60 * 60,'p':'5y'},
	}.get(x)



