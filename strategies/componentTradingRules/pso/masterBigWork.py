#! /usr/bin/python
# -*- coding: UTF-8 -*-
# taskmanager.py
import random, time, Queue
from multiprocessing.managers import BaseManager
import importlib
import sys
sys.path.append('../../')
import utils
from datetime import timedelta  
import pandas as pd

def filtZero(df, key, value):
	return df[df[key] != value]

# 从BaseManager继承的QueueManager:
class QueueManager(BaseManager):
	pass


if __name__=="__main__":
    # 发送任务的队列:
    task_queue = Queue.Queue()
    # 接收结果的队列:
    result_queue = Queue.Queue()
    # 把两个Queue都注册到网络上, callable参数关联了Queue对象:
    QueueManager.register('get_task_queue', callable=lambda: task_queue)
    QueueManager.register('get_result_queue', callable=lambda: result_queue)
    # 绑定端口5000, 设置验证码'abc':
    manager = QueueManager(address=('', 5000), authkey='abc')
    # 启动Queue:
    manager.start()
    # 获得通过网络访问的Queue对象:
    task = manager.get_task_queue()
    result = manager.get_result_queue()
    pdResult = pd.read_csv('run.csv', sep='\t', encoding='utf-8')
    pdResult = pdResult.set_index("datetime")
    pd.DataFrame.mask = filtZero
    print 'read file finished'
    # 将任务放进去
    for i in range(len(pdResult.columns)):
    	effectRows = pdResult.mask(pdResult.columns[i], 0.0)
    	task.put({pdResult.columns[i]:{'date': list(effectRows[pdResult.columns[i]].index), 'value': list(effectRows[pdResult.columns[i]])}})
        if i %100 == 0:
            print "i: " + str(i)

    # 从result队列读取结果:
    print('Try get results...')
    strategyResList = []
    bestRoi =  -99999.99
    bestParameter = ''
    for i in range(len(pdResult.columns)):
    	r = result.get(timeout=20)
    	with open('reslut.txt','a') as file:
    		file.write(str(r))
    		file.write('\n')
    	strategyResList.append(r)
    	roi = r.values()[0][0]
    	if bestRoi < roi:
    		bestParam = r.keys()[0]
    		bestRoi = roi
    		with open('bestRecord.txt','a') as file:
    			file.write("\nbestParam" + str(bestParam))
    			file.write("\tbestRoi" + str(bestRoi))
    			file.write('\n')
    # 关闭:
    manager.shutdown()