#! /usr/bin/python
# -*- coding: UTF-8 -*-
# taskworker.py

import random, time, Queue
from multiprocessing.managers import BaseManager
import importlib
import sys
sys.path.append('../../')
import utils
from datetime import timedelta  
import pandas as pd
import datetime

# 创建类似的QueueManager:
class QueueManager(BaseManager):
    pass


# task.put({result.columns[i]:effectRows[result.columns[i]]})
def run(executeDict):
	cap = 10000.00
	oriCap = 10000.00
	execList = []
	state = False
	stockNum = 0.0
	# print executeDict.values()[0]
	# for date, signal in executeDict.values()[0]:
	for (date, signal) in zip(executeDict.values()[0].get('date'),executeDict.values()[0].get('value')):
		#if the singal is buy(>0) and the state is False that no hold any stock,will excute buy
		#the execute price is just the adjclose price that day's singal.
		if (signal > 0) and (state == False):
			stockNum = cap/stockData.loc[date]["adjclose"]
			# stockNum = cap/stockData.loc[stockData["datetime"] == date]["close"].values[0]
			state = True
			execList.append((date,"buy",stockNum))
		#if the singal is Sell(<0) and the state is True that held stocks,will execute sell				
		if signal < 0 and state:
			cap = stockData.loc[date]["adjclose"]* stockNum
			# cap = stockData.loc[stockData["datetime"] == date]["close"].values[0]* stockNum
			stockNum = 0.0
			state = False
			execList.append((date,"sell",cap))
		
	if state:
		cap = stockData.iloc[-1].adjclose * stockNum
	roi = (cap-oriCap)/oriCap
	result = {str(executeDict.keys()[0]) : (roi, execList)}
	return result

if __name__=="__main__":
	# 由于这个QueueManager只从网络上获取Queue，所以注册时只提供名字:
	QueueManager.register('get_task_queue')
	QueueManager.register('get_result_queue')
	stockData = utils.getStockDataTrain('2018', False)
	stockData = stockData.set_index("datetime")
	stockData.index = stockData.index.map(unicode) 
	# 连接到服务器，也就是运行taskmanager.py的机器:
	server_addr = '127.0.0.1'
	print('Connect to server %s...' % server_addr)
	# 端口和验证码注意保持与taskmanager.py设置的完全一致:
	m = QueueManager(address=(server_addr, 5000), authkey='abc')
	# 从网络连接:
	m.connect()
	# 获取Queue的对象:
	task = m.get_task_queue()
	result = m.get_result_queue()

	while (1):
		try:
			n = task.get(timeout=1)
			r = run(n)
			result.put(r)
		except Queue.Empty:
			print('task queue is empty.')

	# 处理结束:
	print('worker exit.')	
	






