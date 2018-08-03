# coding: utf-8
from numpy import *
import random
from math import sin, sqrt
import sys
sys.path.append('/Users/shiqipan/code/python/playground')
from smaTrading import smaCross

iterMax = 10000
# popSize the particles number in the paper, there are 5 particles.
popSize = 5
#dimensions is the size of the parameter eg, sma 8 parameters .
dimensions = 8
c1 = 2
c2 = 2
errCrit = 0.00001
#equation: Vi(t+1) = w * Vi(t) + c1*randomi1(t)(Pi(t) - Xi(t)) + c2*random2(t)*(Pg(t) - Xi(t))
#equation: Xi(t+1) = Xi(t) + Vi(t+1)
# here i is the ith of the vector, and the t is the tth iteration.

class Particle:
	pass

#initialize the particles
def initParticles():
	particles = []
	for i in range(popSize):
		p = Particle()
		p.params = array([random.randint(1, 200) for i in range(dimensions)])
		p.v = array([random.randint(-80, 80) for i in range(dimensions)])
		p.fitness = smaCross(p.params.tolist())
		# print p.params
		# print p.v
		# print p.fitness
		particles.append(p)
		p.best = p.params
	return particles	

def psosma():
	particles = initParticles()
	VMax = 80
	Vs = 1
	w = 1.3
	# let the first particle be the global best
	gbest = particles[0]
	i = 0
	while i < iterMax :
		for p in particles:
			fitness = smaCross(p.params.tolist())
			if fitness > p.fitness:
				#update the p'th best record.
				p.fitness = fitness
				p.best = p.params
				#update the global best record.
			if fitness > gbest.fitness:
				print "fitness global:" + str(p.fitness)
				gbest = p
			# print "p.v" + str(p.v)
			#update vola
			v = w * p.v + c1 * random.random() * (p.best - p.params) + c2 * random.random() * (gbest.params - p.params)
			v[v > VMax] = VMax
			v[v < (-1 * VMax)] = (-1 * VMax)
			v[abs(v) < Vs] = (-1 * VMax) + 2*VMax*random.random()
			v = v.astype(int)
			# print "v.tolist():" + str(v.tolist())
			#update parmas.
			p.parmas = p.params + v
		i += 1
		if i % (iterMax/10) == 0:
			print '.'
	print '\nParticle Swarm Optimisation\n'
	print 'PARAMETERS\n','-'*9
	print 'Population size : ', popSize
	print 'Dimensions	  : ', dimensions
	print 'Error Criterion : ', errCrit
	print 'c1			  : ', c1
	print 'c2			  : ', c2
	print 'function		:  f6'

	print 'RESULTS\n', '-'*7
	print 'gbest fitness   : ', gbest.fitness
	print 'gbest params	: ', gbest.params
	print 'gbest params	: ', gbest.params

	print 'iterations	  : ', i+1
		
psosma()
