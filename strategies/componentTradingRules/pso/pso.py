# coding: utf-8
from numpy import *
import random
from math import sin, sqrt
from backtest import runbackTest
import sys
sys.path.append('../../')
sys.path.append('../')
import utils
import copy
import importlib

import logging
log = logging.getLogger(__name__)


# The base class of 
# Including stopping condition (cause this part is related with pso iterate can not write separetely.)
# add other kind of PSO only need to change the adjParam() that the way change the params




# popSize the particles number in the paper, there are 5 particles.


#equation: Vi(t+1) = w * Vi(t) + c1*randomi1(t)(Pi(t) - Xi(t)) + c2*random2(t)*(Pg(t) - Xi(t))
#equation: Xi(t+1) = Xi(t) + Vi(t+1)
# here i is the ith of the vector, and the t is the tth iteration.
class Particle:
	pass

class ParticleSwarmOp:
	
	#set the pso basic param
	def __init__(self):
		pass

	def setStrategy(self, strategyName):
		module = importlib.import_module(strategyName)
		class_ = getattr(module, strategyName)
		strategy = class_()
		self.strategyName = strategy.strategyName
		self.strategy = strategy
		self.searchParams = strategy.defaultParam()
		self.dimensions = len(self.searchParams)
		self.iterMax = 1
		for key, value in self.searchParams.items():
			self.iterMax = self.iterMax * len(value)
		self.iterMax = self.iterMax/10
		

	#initialize the particles
	def initParticles(self):
		particles = []
		for i in range(self.popSize):
			p = Particle()
			p.params = {}
			p.v = {}
			p.execparm = {}
			for key, value in self.searchParams.items():
				log.info("(len(value) - 1)"+(len(value) - 1))
				log.info("self.popSize"+self.popSize)
				log.info("key,value:" + key + value)
				#keep each Particle began to search in the different part
				t = random.randint(((len(value) - 1)/self.popSize) * i, ((len(value) - 1)/self.popSize) * (i + 1) )
				p.params[key] = t
				p.execparm[key] = []
				p.execparm[key].append(value[t])
				p.v[key] = random.randint(0, len(value))	
			_, best = runbackTest(self.stockData, self.strategy, **p.execparm)
			p.fitness = float(best[1])	
			particles.append(p)
			p.best = p
			# print best
		self.particles = particles

	# used to initial parameter
	def initParameters(self):
		self.c1 = 2
		self.c2 = 2
		self.w = 0.9
		# self.errCrit = 0.00001
		self.popSize = 5
		# self.iterMax = 50
		# self.stockData = utils.getStockDataTrain("0005", True)
		self.psoName = 'basic PSO'
		return

		

	# This a common part that used to process as procedure of PSO.
	def pso(self, strategyName, code, stratDate, endDate):

		self.setStrategy(strategyName)
		self.iterMax = 50
		log.info('max Iterate: ' + str(self.iterMax))

		# self.stockData = utils.getStockDataWithTime(code, stratDate, endDate)
		self.stockData = utils.getStockDataWithTimeFromCSV(code, stratDate, endDate)
		self.initParameters()
		self.initParticles()
		# let the first particle be the global best
		self.gbest = copy.deepcopy(self.particles[0])
		fitness = 0.0
		self.iterCnt = 0
		# while fitness < goalFittness and i < 50:
		# self.stopConMaxDist(0.5)
		self.stopWithMaxIterCnt()
		# print "self.iterMax: " + str(self.iterMax)
		# self.stopConImpBest(self.iterMax/2)
		log.info("find one%s,%s", self.gbest.execparm, self.gbest.params)				
		log.info('\nParticle Swarm Optimisation\n')
		log.info('PARAMETERS\n' + '-'*9)
		log.info('Population size : %s', self.popSize)
		log.info('Dimensions	  : %s', self.dimensions)
		log.info('ParticleSwarmOp Name :%s', self.psoName)
		log.info('stop Condition :%s', self.stopCondition)
		log.info('strategyName: %s', strategyName)
		log.info('stockCode: %s', code)
		log.info('RESULTS\n' + '-'*7)
		log.info('ROI   : %s', self.gbest.fitness)
		log.info('gbest params	: %s', self.gbest.params)
		log.info('gbest execparm	: %s', self.gbest.execparm)
		log.info('iterations	  : %s', self.iterCnt)
		# record = 'strategyName:\t' + str(self.strategyName) + '\tcode:\t' + str(code) + '\texecparm:\t' \
		# + str(self.gbest.execparm) + '\tROI:\t' + str(self.gbest.fitness)
		record = str(self.strategyName) + '\t' + str(code) + '\t' \
		+ str(self.gbest.execparm) + '\t' + str(self.gbest.fitness) + '\n'
		return record

	def paramAdj(self, p):
		tempExecParams = dict()
		while not self.strategy.checkParams(**tempExecParams):
			for key, value in self.searchParams.items():
				#base on the function: V(t+1) = w*V(t) + C1*r1*(pbest - p[t]) + C2*r2*(gbest - p[t])
				p.v[key] = int(self.w * p.v[key] + self.c1 * random.random() * (p.best.params[key] - p.params[key]) + \
					self.c2 * random.random() * (self.gbest.params[key] - p.params[key]))
				log.debug("key:" + str(key) + "\tv: " + str(p.v) + "\t param:" + str(p.params)) 
				p.params[key] = (p.params[key] + p.v[key]) % (len(value))

				tempExecParams[key] = []
				tempExecParams[key].append(value[p.params[key]])
		p.execparm = tempExecParams

	#blow is the stop condition
	def stopWithMaxIterCnt(self):
		self.stopCondition = 'stopWithMaxIterCnt'
		while (self.iterCnt < self.iterMax ):
			self.iterCnt += 1
			for p in self.particles:
				_, bestfitness = runbackTest(self.stockData, self.strategy, **p.execparm)
				fitness = bestfitness[1]
				
				if fitness > p.fitness:
					#update the p'th best record.
					p.fitness = fitness
					p.best = p
					#update the global best record.
				if fitness > self.gbest.fitness:
					log.info('find one ' + str(p.execparm) + ' ' +  str(p.params) + ' at ' + str(self.iterCnt) + ' iterations.')
					self.gbest = copy.deepcopy(p)
				self.paramAdj(p)		

	#return True means continue test;False will stop
	def stopConMaxDist(self, distThreshold):
		self.stopCondition = 'stopConMaxDist'
		stop = False
		self.distThreshold = distThreshold
		while (not stop) and (self.iterCnt < self.iterMax ):
			dist = 0.0
			self.iterCnt += 1
			for p in self.particles:
				_, bestfitness = runbackTest(self.stockData, self.strategy, **p.execparm)
				# print bestfitness
				fitness = bestfitness[1]
				
				if fitness > p.fitness:
					#update the p'th best record.
					p.fitness = fitness
					p.best = p
					#update the global best record.
				if fitness > self.gbest.fitness:
					self.gbest = copy.deepcopy(p)
					log.info('find one ' + str(p.execparm) + ' ' +  str(p.params) + ' at ' + str(self.iterCnt) + ' iterations.') 


				if self.iterCnt > self.iterMax/4:
					if abs(fitness - self.gbest.fitness) > dist:
						dist = abs(fitness - self.gbest.fitness)
						# log.debug( "dist:" + str(dist) + "result from: " + str(fitness) + str(self.gbest.fitness))
						# log.debug("execparm:" + str(p.execparm))
						# log.debug("gbestexecparm: " + str(self.gbest.execparm))
					if dist > self.distThreshold:
						stop = True
				self.paramAdj(p)								

	def stopConImpBest(self, t):
		self.stopCondition = 'stopConImpBest'
		stop = False
		self.stopThreshold  = t
		keepCnt = 0
		while (not stop) and (self.iterCnt < self.iterMax ):
			keepCnt += 1
			self.iterCnt += 1
			for p in self.particles:
				_, bestfitness = runbackTest(self.stockData, self.strategy, **p.execparm)
				# print bestfitness
				fitness = bestfitness[1]
				
				if fitness > p.fitness:
					#update the p'th best record.
					p.fitness = fitness
					p.best = p
					#update the global best record.
				if fitness > self.gbest.fitness:
					log.info('find one ' + str(p.execparm) + ' ' +  str(p.params) + ' at ' + str(self.iterCnt) + ' iterations.')
					# print("original one%s,%s", self.gbest.execparm, self.gbest.params)
					self.gbest = copy.deepcopy(p)
					keepCnt = 0
				self.paramAdj(p)

			if keepCnt > self.stopThreshold:
					log.info('will stop ' + str(keepCnt ))
					stop = True				

def runSTO():
	allHsiCode = ['2018']	
	allStrategy = ['StochasticOscillator']
	# allStrategy = ['MovingAverage', 'OnBalanceVolAve', 'RelativeStrengthIndex', 'tradingRangeBreakout','MacdHistogram','BollingerBandsStrategy']
	codeName = {'5': 'HSBCHoldings', '11': 'HangSengBank', '23': 'BankofEAsia', '388': 'HKEx', '939': 'CCB', '1299': 'AIA', '1398': 'ICBC', '2318': 'PingAn', '2388': 'BOCHongKong', '2628': 'ChinaLife', '3328': 'Bankcomm', '3988': 'BankofChina', '2': 'CLPHoldings', '3': 'HK&ChinaGas', '6': 'PowerAssets', '836': 'ChinaResPower', '1038': 'CKIHoldings', '12': 'HendersonLand', '16': 'SHKPpt', '17': 'NewWorldDev', '83': 'SinoLand', '101': 'HangLungPpt', '688': 'ChinaOverseas', '823': 'LinkREIT', '1109': 'ChinaResLand', '1113': 'CKAsset', '1997': 'WharfREIC', '2007': 'CountryGarden', '1': 'CKHHoldings', '19': 'SwirePacificA', '27': 'GalaxyEnt', '66': 'MTRCorporation', '144': 'ChinaMerPort', '151': 'WantWantChina', '175': 'GeelyAuto', '267': 'CITIC', '288': 'WHGroup', '386': 'SinopecCorp', '700': 'Tencent', '762': 'ChinaUnicom', '857': 'PetroChina', '883': 'CNOOC', '941': 'ChinaMobile', '992': 'LenovoGroup', '1044': 'HenganIntl', '1088': 'ChinaShenhua', '1928': 'SandsChinaLtd', '2018': 'AACTech', '2319': 'MengniuDairy', '2382': 'SunnyOptical'}
	pso = ParticleSwarmOp()
	for strategy in allStrategy:
		import time
		start = time.time()
		for code in allHsiCode:	
			record = pso.pso(strategy, code, '2013-07-13', '2016-12-12')
			record = codeName.get(code) + '\t' + str(record)
			print(record)
		end = time.time()
		escape = end - start
		print(strategy,escape)

def testAll():
	import time
	start = time.time()
	# stockDataTrain = utils.getStockDataTrain("0005", True)
	allHsiCode = ['5', '11', '23', '388', '939', '1299', '1398', '2318', '2388', '2628', '3328', '3988', \
	'2', '3', '6', '836', '1038', '12', '16', '17', '83', '101', '688', '823', '1109', '1113',  '2007', \
	'1', '19', '27', '66', '144', '151', '175', '267', '288', '386', '700', '762', '857', '883', '941', '992', \
	'1044', '1088', '1928', '2018', '2319', '2382']

	# allHsiCode = ['2382', '19', '151', '1044']
	allStrategy = ['MovingAverage', 'BollingerBandsStrategy', 'MacdHistogram', 'RelativeStrengthIndex', 'OnBalanceVolAve', 'tradingRangeBreakout','StochasticOscillator']

	# allStrategy = ['StochasticOscillator']
	# codeName = {'2382': 'SunnyOptical'}
	codeName = {'5': 'HSBCHoldings', '11': 'HangSengBank', '23': 'BankofEAsia', '388': 'HKEx', '939': 'CCB', '1299': 'AIA', '1398': 'ICBC', '2318': 'PingAn', '2388': 'BOCHongKong', '2628': 'ChinaLife', '3328': 'Bankcomm', '3988': 'BankofChina', '2': 'CLPHoldings', '3': 'HK&ChinaGas', '6': 'PowerAssets', '836': 'ChinaResPower', '1038': 'CKIHoldings', '12': 'HendersonLand', '16': 'SHKPpt', '17': 'NewWorldDev', '83': 'SinoLand', '101': 'HangLungPpt', '688': 'ChinaOverseas', '823': 'LinkREIT', '1109': 'ChinaResLand', '1113': 'CKAsset', '1997': 'WharfREIC', '2007': 'CountryGarden', '1': 'CKHHoldings', '19': 'SwirePacificA', '27': 'GalaxyEnt', '66': 'MTRCorporation', '144': 'ChinaMerPort', '151': 'WantWantChina', '175': 'GeelyAuto', '267': 'CITIC', '288': 'WHGroup', '386': 'SinopecCorp', '700': 'Tencent', '762': 'ChinaUnicom', '857': 'PetroChina', '883': 'CNOOC', '941': 'ChinaMobile', '992': 'LenovoGroup', '1044': 'HenganIntl', '1088': 'ChinaShenhua', '1928': 'SandsChinaLtd', '2018': 'AACTech', '2319': 'MengniuDairy', '2382': 'SunnyOptical'}
	# allStrategy = ['MovingAverage','BollingerBandsStrategy']
	# allHsiCode = ['5', '11', '23', '388']

	pso = ParticleSwarmOp()

	# pso.pso( "BollingerBandsStrategy")
	fileObject = open('PsoResult2', 'w+')	
	for strategy in allStrategy:
		for code in allHsiCode:	
			# record = pso.pso(strategy, code, '2015-07-15', '2017-07-15')
			# bf.setStockDataTime(code, '2013-07-13', '2016-12-12')
			record = pso.pso(strategy, code, '2013-07-13', '2016-12-12')
			record = codeName.get(code) + '\t' + str(record)
			fileObject.write(record)
	
	fileObject.close()
	end = time.time()
	escape = end - start
	log.info(escape)

if __name__=="__main__":
	# testAll()
	# runSTO()
	# if(len(sys.argv) <= 2):
	# 	log.error("enter startegy name,stock code")
	
	# else:
	# 	pso = ParticleSwarmOp();
	# 	pso.pso(sys.argv[1], sys.argv[2],'2013-07-13', '2016-12-12')
	
	pso = ParticleSwarmOp()
	# pso.pso( "MacdHistogram")
	pso.pso( "MovingMomentum", '5','2013-07-13', '2016-12-12')
	# pso.pso( "RelativeStrengthIndex")
	# pso.pso( "MovingAverage")
	# pso.pso( "MovingAveConvergeDiver")
	# pso.pso( "OnBalanceVolAve")
	# pso.pso( "tradingRangeBreakout")
	

