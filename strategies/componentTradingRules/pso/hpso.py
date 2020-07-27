# implement the HPSO(self-organizing hierarchical particle swarm optimizer) that  describe in the paper:
#	"self-Organizing Hierarchical Particle Swarm Optimizer With Time-Varying Acceleration Coefficients"

# coding: utf-8
import numpy
import random
from math import sin, sqrt
import sys
sys.path.append('../../')
from backtest import runbackTest

import utils
import copy
import importlib
import pso

#equation: Vi(t+1) = w * Vi(t) + c1*randomi1(t)(Pi(t) - Xi(t)) + c2*random2(t)*(Pg(t) - Xi(t))
#equation: Xi(t+1) = Xi(t) + Vi(t+1)
# here i is the ith of the vector, and the t is the tth iteration.

class Particle:
	pass

class HierarchinalParticleSwarmOp(pso.ParticleSwarmOp):
	def initParameters(self):
		self.popSize = 5
		self.randSize = self.iterMax*self.popSize*self.dimensions
		self.r1 = numpy.random.uniform(size=self.randSize)
		self.r2 = numpy.random.uniform(size=self.randSize)
		self.r3 = numpy.random.uniform(size=self.randSize)
		self.r4 = numpy.random.uniform(size=self.randSize)
		self.r5 = numpy.random.uniform(size=self.randSize)
		self.wmax = 2
		self.wmin = 0.4
		self.c1 = 2
		self.c2 = 2
		self.randCnt = 0
		# self.stockData = utils.getStockDataTrain("0005", True)

	
	def paramAdj(self, p):
		self.psoName = 'HPSO'
		tempExecParams = dict()
		# the key point for the self-oranizing hierarchical is to reinitialization the velocities
		# Using a time-varying reinitialization velocity strategy max velocity is len(value)
		
		while not self.strategy.checkParams(**tempExecParams):	
			for key, value in self.searchParams.items():
				# v = float((len(value)-1)/4) * float(self.iterCnt)/self.popSize)
				v = (len(value)-1) * (1-float(self.iterCnt)/self.iterMax)
				# print "v: " + str(v)
				self.randCnt = (self.randCnt + 1)%self.randSize
				#base on the function: V(t+1) = w*V(t) + C1*r1*(pbest - p[t]) + C2*r2*(gbest - p[t])
				# p.v[key] = int(w * p.v[key] + c1 * random.random() * (p.best.params[key] - p.params[key]) + c2 * random.random() * (gbest.params[key] - p.params[key]))
				# self.w = (self.wmax - self.wmin) * (self.iterMax - self.iterCnt)/self.iterMax + self.wmin
				self.w = 0
				p.v[key] = self.w * p.v[key] + self.c1*self.r1[self.randCnt]*(p.best.params[key] - p.params[key]) + self.c2*self.r2[self.randCnt]*(self.gbest.params[key] - p.params[key])
				if (p.v[key] == 0):
					if self.r3[self.randCnt] < 0.5:
						p.v[key] = self.r4[self.randCnt]  * v
					else:
						p.v[key] = self.r5[self.randCnt] * v
				
				p.v[key] = numpy.sign(p.v[key]) * min(abs(v), len(value)-1)															
				p.params[key] = int((p.params[key] + p.v[key]) % (len(value)))
				tempExecParams[key] = []
				tempExecParams[key].append(value[p.params[key]])
		# print "\tparams:" + str(tempExecParams)			

		p.execparm = tempExecParams				



if __name__=="__main__":

	allHsiCode = ['2382', '19', '151', '1044']
	allStrategy = ['MovingMomentum']
	codeName = {'5': 'HSBCHoldings', '11': 'HangSengBank', '23': 'BankofEAsia', '388': 'HKEx', '939': 'CCB', '1299': 'AIA', '1398': 'ICBC', '2318': 'PingAn', '2388': 'BOCHongKong', '2628': 'ChinaLife', '3328': 'Bankcomm', '3988': 'BankofChina', '2': 'CLPHoldings', '3': 'HK&ChinaGas', '6': 'PowerAssets', '836': 'ChinaResPower', '1038': 'CKIHoldings', '12': 'HendersonLand', '16': 'SHKPpt', '17': 'NewWorldDev', '83': 'SinoLand', '101': 'HangLungPpt', '688': 'ChinaOverseas', '823': 'LinkREIT', '1109': 'ChinaResLand', '1113': 'CKAsset', '1997': 'WharfREIC', '2007': 'CountryGarden', '1': 'CKHHoldings', '19': 'SwirePacificA', '27': 'GalaxyEnt', '66': 'MTRCorporation', '144': 'ChinaMerPort', '151': 'WantWantChina', '175': 'GeelyAuto', '267': 'CITIC', '288': 'WHGroup', '386': 'SinopecCorp', '700': 'Tencent', '762': 'ChinaUnicom', '857': 'PetroChina', '883': 'CNOOC', '941': 'ChinaMobile', '992': 'LenovoGroup', '1044': 'HenganIntl', '1088': 'ChinaShenhua', '1928': 'SandsChinaLtd', '2018': 'AACTech', '2319': 'MengniuDairy', '2382': 'SunnyOptical'}

	pso = HierarchinalParticleSwarmOp()

	# pso.pso( "BollingerBandsStrategy")
		
	for strategy in allStrategy:
		fileObject = open(strategy+'Result', 'w+')
		for code in allHsiCode:	
			record = pso.pso( strategy, code,'2015-01-01','2018-12-31')
			record = codeName.get(code) + '\t' + record
			fileObject.write(record)
		fileObject.close()	
