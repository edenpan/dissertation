# coding: utf-8
from numpy import *
import random
from math import sin, sqrt
from backtest import runbackTest
import sys
sys.path.append('../')
import utils
import copy
import importlib


# popSize the particles number in the paper, there are 5 particles.


#equation: Vi(t+1) = w * Vi(t) + c1*randomi1(t)(Pi(t) - Xi(t)) + c2*random2(t)*(Pg(t) - Xi(t))
#equation: Xi(t+1) = Xi(t) + Vi(t+1)
# here i is the ith of the vector, and the t is the tth iteration.
class Particle:
	pass

class ParticleSwarmOp:
	
	#set the pso basic param
	def __init__(self):
		self.c1 = 2
		self.c2 = 2
		self.w = 1.3
		self.errCrit = 0.00001
		self.popSize = 5
		self.iterMax = 30
		self.stockData = utils.getStockDataTrain("0005", True)
		

	def setStrategy(self, strategyName):
		module = importlib.import_module(strategyName)
		class_ = getattr(module, strategyName)
		strategy = class_()
		self.strategyName = strategy.strategyName
		self.strategy = strategy
		self.searchParams = strategy.defaultParam()
		self.dimensions = len(self.searchParams)
		

	#initialize the particles
	def initParticles(self):
		particles = []
		for i in range(self.popSize):
			p = Particle()
			p.params = {}
			p.v = {}
			p.execparm = {}
			for key, value in self.searchParams.iteritems():

				t = random.randint(0, len(value) - 1)
				p.params[key] = t
				p.execparm[key] = []
				p.execparm[key].append(value[t])
				p.v[key] = random.randint(0, len(value))	
			print p.execparm
			_, best = runbackTest(self.stockData, self.strategy, **p.execparm)
			p.fitness = float(best[1])	
			particles.append(p)
			p.best = p
		self.particles = particles

	def pso(self, strategyName):
		self.setStrategy(strategyName)
		self.initParticles()
		
		# let the first particle be the global best
		self.gbest = copy.deepcopy(self.particles[0])
		# goalFittness = 0.17
		fitness = 0.0
		self.iterCnt = 0
		# while fitness < goalFittness and i < 50:
		while self.iterCnt < self.iterMax:
			for p in self.particles:
				_, bestfitness = runbackTest(self.stockData, self.strategy, **p.execparm)
				
				print bestfitness
				fitness = bestfitness[1]
				# print "Fitness:" + str(bestfitness[1])
				if fitness > p.fitness:
					#update the p'th best record.
					p.fitness = fitness
					p.best = p
					#update the global best record.
				if fitness > self.gbest.fitness:
					# print("find one%s,%s", p.execparm, p.params)
					self.gbest = copy.deepcopy(p)
				self.paramAdj(p)
			self.iterCnt += 1

		print("find one%s,%s", self.gbest.execparm, self.gbest.params)				
		print '\nParticle Swarm Optimisation\n'
		print 'PARAMETERS\n','-'*9
		print 'Population size : ', self.popSize
		print 'Dimensions	  : ', self.dimensions
		print 'c1			  : ', self.c1
		print 'c2			  : ', self.c2
		print 'function		:  f6'
		print 'RESULTS\n', '-'*7
		print 'gbest fitness   : ', self.gbest.fitness
		print 'gbest params	: ', self.gbest.params
		print 'gbest execparm	: ', self.gbest.execparm
		print 'iterations	  : ', self.iterCnt
		for p in self.particles:
			print 'particles	  : ', p.execparm

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


if __name__=="__main__":
	# stockDataTrain = utils.getStockDataTrain("0005", True)
	pso = ParticleSwarmOp()

	# pso.pso( "BollingerBandsStrategy")
	pso.pso( "MovingAverage")
	# pso.pso( "RelativeStrengthIndex")
	
	# pso(stockDataTrain, "BollingerBands")

