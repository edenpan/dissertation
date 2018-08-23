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
from  bb import BollingerBands
from  bb import defaultParam as bbDefualtParams
from  bb import parseparams as bbparseparams
iterMax = 10000
# popSize the particles number in the paper, there are 5 particles.

#dimensions is the size of the parameter eg, sma 8 parameters .
c1 = 2
c2 = 2
w = 0.5 + (numpy.random.uniform()/2)
errCrit = 0.00001
popSize = 5
params = globals()["bbDefualtParams"]()
dimensions = len(params)
#equation: Vi(t+1) = w * Vi(t) + c1*randomi1(t)(Pi(t) - Xi(t)) + c2*random2(t)*(Pg(t) - Xi(t))
#equation: Xi(t+1) = Xi(t) + Vi(t+1)
# here i is the ith of the vector, and the t is the tth iteration.

class Particle:
	pass

#initialize the particles
def initParticles(strategyName, stockData):
	particles = []
	for i in range(popSize):
		p = Particle()
		p.params = {}
		p.v = {}
		p.execparm = {}
		for key, value in params.iteritems():
			t = random.randint(0, len(value) - 1)
			p.params[key] = t
			p.execparm[key] = []
			p.execparm[key].append(value[t])
			p.v[key] = random.randint(0, len(value))	
		
		_, best = runbackTest(stockData, strategyName, True, **p.execparm)
		p.fitness = float(best[1])	
		particles.append(p)
		p.best = p
		
	return particles	

def pso(stockData, strategyName):
	particles = initParticles(strategyName, stockData)
	VMax = len(params)
	Vs = 1
	
	# let the first particle be the global best
	gbest = copy.deepcopy(particles[0])
	print("original%s,%s", gbest.execparm, gbest.params)
	goalFittness = 0.17
	fitness = 0.0
	i = 0
	iterMax = 50
	r1 = numpy.random.uniform(size=iterMax*len(particles)*dimensions)
	r2 = numpy.random.uniform(size=iterMax*len(particles)*dimensions)
	r3 = numpy.random.uniform(size=iterMax*len(particles)*dimensions)
	r4 = numpy.random.uniform(size=iterMax*len(particles)*dimensions)
	r5 = numpy.random.uniform(size=iterMax*len(particles)*dimensions)
	randCnt = 0
	# while fitness < goalFittness and i < 50:
	while i < iterMax:
		for p in particles:
			_, bestfitness = runbackTest(stockData, strategyName, **p.execparm)
			
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


			for key, value in params.iteritems():
				v = len(value)-1
				#base on the function: V(t+1) = w*V(t) + C1*r1*(pbest - p[t]) + C2*r2*(gbest - p[t])
				# p.v[key] = int(w * p.v[key] + c1 * random.random() * (p.best.params[key] - p.params[key]) + c2 * random.random() * (gbest.params[key] - p.params[key]))
				p.v[key] = c1*r1[randCnt]*(p.best.params[key] - p.params[key]) + c2*r2[randCnt]*(gbest.params[key] - p.params[key])
				if (p.v[key] == 0):
					if r3[randCnt] < 0.5:
						p.v[key] = r4[randCnt]  * v
					else:
						p.v[key] = r5[randCnt] * v
				p.v[key] = numpy.sign(p.v[key]) * min(abs(v), len(value)-1)																	
				p.params[key] = int((p.params[key] + p.v[key]) % (len(value)))
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
	print 'w 			 : ', w
	print (gbest)
	print 'RESULTS\n', '-'*7
	print 'gbest fitness   : ', gbest.fitness
	print 'gbest params	: ', gbest.params
	print 'gbest execparm	: ', gbest.execparm

	print 'iterations	  : ', i
	for p in particles:
		print 'particles	  : ', p.execparm


if __name__=="__main__":	
	stockDataTrain = utils.getStockDataTrain("0005", True)	
	pso(stockDataTrain, "BollingerBands")
