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
		for key, value in self.searchParams.iteritems():
			self.iterMax = self.iterMax * len(value)
		self.iterMax = self.iterMax/20
		

	#initialize the particles
	def initParticles(self):
		particles = []
		for i in range(self.popSize):
			p = Particle()
			p.params = {}
			p.v = {}
			p.execparm = {}
			for key, value in self.searchParams.iteritems():
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
			print best
		self.particles = particles

	# used to initial parameter
	def initParameters(self):
		self.c1 = 2
		self.c2 = 2
		self.w = 0.9
		# self.errCrit = 0.00001
		self.popSize = 5
		self.iterMax = 50
		self.stockData = utils.getStockDataTrain("0005", True)
		self.psoName = 'basic PSO'
		return

	# This a common part that used to process as procedure of PSO.
	def pso(self, strategyName):
		self.setStrategy(strategyName)
		self.initParameters()
		self.initParticles()

		
		# let the first particle be the global best
		self.gbest = copy.deepcopy(self.particles[0])
		fitness = 0.0
		self.iterCnt = 0
		# while fitness < goalFittness and i < 50:
		# self.stopConMaxDist( 0.5)
		# self.stopWithMaxIterCnt()
		# print "self.iterMax: " + str(self.iterMax)
		self.stopConImpBest(self.iterMax/4)
		print("find one%s,%s", self.gbest.execparm, self.gbest.params)				
		print '\nParticle Swarm Optimisation\n'
		print 'PARAMETERS\n','-'*9
		print 'Population size : ', self.popSize
		print 'Dimensions	  : ', self.dimensions
		print 'ParticleSwarmOp Name :', self.psoName
		print 'stop Condition :', self.stopCondition
		print 'strategyName:', strategyName
		print 'RESULTS\n', '-'*7
		print 'gbest fitness   : ', self.gbest.fitness
		print 'gbest params	: ', self.gbest.params
		print 'gbest execparm	: ', self.gbest.execparm
		print 'iterations	  : ', self.iterCnt
		

	def paramAdj(self, p):
		tempExecParams = dict()
		while not self.strategy.checkParams(**tempExecParams):
			for key, value in self.searchParams.iteritems():
				#base on the function: V(t+1) = w*V(t) + C1*r1*(pbest - p[t]) + C2*r2*(gbest - p[t])
				p.v[key] = int(self.w * p.v[key] + self.c1 * random.random() * (p.best.params[key] - p.params[key]) + self.c2 * random.random() * (self.gbest.params[key] - p.params[key]))
				# print "key:" + str(key) + "\tv: " + str(p.v) + "\t param:" + str(p.params)
				p.params[key] = (p.params[key] + p.v[key]) % (len(value))
				# print "key" + str(key) + "\tparams:" + str(p.params)	
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
				print bestfitness
				fitness = bestfitness[1]
				
				if fitness > p.fitness:
					#update the p'th best record.
					p.fitness = fitness
					p.best = p
					#update the global best record.
				if fitness > self.gbest.fitness:
					print 'find one ' + str(p.execparm) + ' ' +  str(p.params) + ' at ' + str(self.iterCnt) + ' iterations.'
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
				print bestfitness
				fitness = bestfitness[1]
				
				if fitness > p.fitness:
					#update the p'th best record.
					p.fitness = fitness
					p.best = p
					#update the global best record.
				if fitness > self.gbest.fitness:
					self.gbest = copy.deepcopy(p)
					print 'find one ' + str(p.execparm) + ' ' +  str(p.params) + ' at ' + str(self.iterCnt) + ' iterations.'

				if self.iterCnt > self.iterMax/4:
					if abs(fitness - self.gbest.fitness) > dist:
						dist = abs(fitness - self.gbest.fitness)
						# print "dist:" + str(dist) + "result from: " + str(fitness) + str(self.gbest.fitness)
						# print "execparm:" + str(p.execparm)
						# print "gbestexecparm: " + str(self.gbest.execparm)
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
					print 'find one ' + str(p.execparm) + ' ' +  str(p.params) + ' at ' + str(self.iterCnt) + ' iterations.'
					# print("original one%s,%s", self.gbest.execparm, self.gbest.params)
					self.gbest = copy.deepcopy(p)
					keepCnt = 0
				self.paramAdj(p)

			if keepCnt > self.stopThreshold:
					print 'will stop ' + str(keepCnt )
					stop = True				


if __name__=="__main__":
	# stockDataTrain = utils.getStockDataTrain("0005", True)
	pso = ParticleSwarmOp()

	# pso.pso( "BollingerBandsStrategy")
	# pso.pso( "MovingAverage")
	pso.pso( "MacdHistogram")
	# pso.pso( "RelativeStrengthIndex")
	# pso.pso( "MovingAverage")
	# pso.pso( "MovingAveConvergeDiver")
	# pso.pso( "OnBalanceVolAve")
	# pso.pso( "tradingRangeBreakout")
	

