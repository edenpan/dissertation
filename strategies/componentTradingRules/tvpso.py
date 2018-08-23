# implement the HPSO(self-organizing hierarchical particle swarm optimizer) that  describe in the paper:
#	"self-Organizing Hierarchical Particle Swarm Optimizer With Time-Varying Acceleration Coefficients"

# coding: utf-8
import numpy
import random
from math import sin, sqrt
from backtest import runbackTest
import sys
sys.path.append('../')
import utils
import copy
import importlib
import pso
#equation: Vi(t+1) = w * Vi(t) + c1*randomi1(t)(Pi(t) - Xi(t)) + c2*random2(t)*(Pg(t) - Xi(t))
#equation: Xi(t+1) = Xi(t) + Vi(t+1)
# here i is the ith of the vector, and the t is the tth iteration.

class Particle:
	pass

class TimeVariantParticleSwarmOp(pso.ParticleSwarmOp):

	def __init__(self):
		self.c1max = 2
		self.c2max = 2
		self.c1min = 0.2
		self.c2min = 0.2
		self.wmax = 2
		self.wmin = 0.2
		self.errCrit = 0.00001
		self.popSize = 5
		self.iterMax = 50
		self.stockData = utils.getStockDataTrain("0005", True)
	
	def paramAdj(self, p):
		print self.iterCnt
		tempExecParams = dict()
		while not self.strategy.checkParams(**tempExecParams):
			tempExecParams = dict()
			for key, value in self.searchParams.iteritems():
				#update c1,c2 and w
				#because c1,c2 and w will keeping decrease and a high possible that decrease into 0 ,that can never go out the loop
				#the problem should solve.
				#wait me to find a more efficent way~
				self.w = (self.wmax-self.wmin) * (self.iterMax-self.iterCnt)/self.iterMax + self.wmin
				self.c1 = (self.c1max-self.c1min) * (self.iterMax-self.iterCnt)/self.iterMax + self.c1min
				self.c2 = (self.c2max-self.c2min) * (self.iterMax-self.iterCnt)/self.iterMax + self.c2min
				
				p.v[key] = int((self.w * p.v[key] + self.c1 * random.random() * (p.best.params[key] - p.params[key]) + self.c2 * random.random() * (self.gbest.params[key] - p.params[key])) * len(value)) 
				print "key:" + str(key) + "\tv: " + str(p.v) + "\t param:" + str(p.params)
				p.params[key] = (p.params[key] + p.v[key]) % (len(value))
				print "key" + str(key) + "\tparams:" + str(p.params)	
				tempExecParams[key] = []
				tempExecParams[key].append(value[p.params[key]])
				print "tempExecParams: " + str(tempExecParams)
		p.execparm = tempExecParams

if __name__=="__main__":	
	pso = TimeVariantParticleSwarmOp()
	pso.pso( "MovingAverage")
