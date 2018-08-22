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
from  ma import defaultParam as maDefualtParams
from  ma import parseparams as maparseparams
from  ma import ma

# popSize the particles number in the paper, there are 5 particles.

#dimensions is the size of the parameter eg, sma 8 parameters .
c1 = 2
c2 = 2
w = 1.3
errCrit = 0.00001
popSize = 5
params = globals()["maDefualtParams"]()
dimensions = len(params)
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
		self.iterMax = 50
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
		for i in range(popSize):
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
		gbest = copy.deepcopy(self.particles[0])
		print("original%s,%s", gbest.execparm, gbest.params)
		# goalFittness = 0.17
		fitness = 0.0
		i = 0
		# while fitness < goalFittness and i < 50:
		while i < 50:
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
				if fitness > gbest.fitness:
					# print("find one%s,%s", p.execparm, p.params)
					gbest = copy.deepcopy(p)
					print(gbest)
				for key, value in self.searchParams.iteritems():
					#base on the function: V(t+1) = w*V(t) + C1*r1*(pbest - p[t]) + C2*r2*(gbest - p[t])
					p.v[key] = int(w * p.v[key] + c1 * random.random() * (p.best.params[key] - p.params[key]) + c2 * random.random() * (gbest.params[key] - p.params[key]))
					p.params[key] = (p.params[key] + p.v[key]) % (len(value))
					p.execparm[key] = []
					p.execparm[key].append(value[p.params[key]])
			i += 1

		print("find one%s,%s", gbest.execparm, gbest.params)		
		print(gbest)		
		print '\nParticle Swarm Optimisation\n'
		print 'PARAMETERS\n','-'*9
		print 'Population size : ', popSize
		print 'Dimensions	  : ', dimensions
		# print 'Error Criterion : ', errCrit
		print 'c1			  : ', c1
		print 'c2			  : ', c2
		print 'function		:  f6'
		print(gbest)
		print 'RESULTS\n', '-'*7
		print 'gbest fitness   : ', gbest.fitness
		print 'gbest params	: ', gbest.params
		print 'gbest execparm	: ', gbest.execparm

		print 'iterations	  : ', i
		for p in self.particles:
			print 'particles	  : ', p.execparm


if __name__=="__main__":	
	# stockDataTrain = utils.getStockDataTrain("0005", True)
	pso = ParticleSwarmOp()

	# pso.pso( "BollingerBandsStrategy")
	pso.pso( "BollingerBandsStrategy")
	
	# pso(stockDataTrain, "BollingerBands")

