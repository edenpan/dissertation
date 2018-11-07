 # implement the HPSO(self-organizing hierarchical particle swarm optimizer) that  describe in the paper:
#	"self-Organizing Hierarchical Particle Swarm Optimizer With Time-Varying Acceleration Coefficients"

# coding: utf-8
import numpy
import random
from math import sin, sqrt
from backtest import runbackTest
import sys
sys.path.append('../../')
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

	def initParameters(self):
		self.c1max = 2
		self.c2max = 2
		self.c1min = 0.2
		self.c2min = 0.2
		self.wmax = 2
		self.wmin = 0.4
		self.errCrit = 0.00001
		self.popSize = 5
		# self.iterMax = 50
		# self.stockData = utils.getStockDataTrain("0005", True)
		self.randomSize = self.iterMax*self.popSize*len(self.searchParams)
		# print "randomSize" + str(self.randomSize)
		self.r1 = numpy.random.uniform(size=self.randomSize)
		self.r2 = numpy.random.uniform(size=self.randomSize)
		self.r3 = numpy.random.uniform(size=self.randomSize)
		self.r4 = numpy.random.uniform(size=self.randomSize)
		self.r5 = numpy.random.uniform(size=self.randomSize)
		self.r6 = numpy.random.uniform(size=self.randomSize)
		self.randCnt = 0
		
		
	def paramAdj(self, p):
		self.psoName = 'TVPSO'
		tempExecParams = dict()
		self.w = (self.wmax - self.wmin) * (self.iterMax - self.iterCnt)/self.iterMax + self.wmin
		self.c1 = self.c1max - (self.c1max-self.c1min) * (self.iterMax-self.iterCnt)/self.iterMax
		self.c2 = (self.c2max-self.c2min) * (self.iterMax-self.iterCnt)/self.iterMax + self.c2min
		while not self.strategy.checkParams(**tempExecParams):
			tempExecParams = dict()
			for key, value in self.searchParams.iteritems():
				self.randCnt = (self.randCnt + 1)%self.randomSize
				#update c1,c2 and w
				#because c1,c2 and w will keeping decrease and a high possible that decrease into 0 ,that can never go out the loop
				#the problem should solve.
				
				p.v[key] = int((self.w * p.v[key] + self.c1 * self.r1[self.randCnt] * (p.best.params[key] - p.params[key]) + self.c2 * self.r2[self.randCnt] * (self.gbest.params[key] - p.params[key])))
				p.params[key] = int((p.params[key] + p.v[key]) % (len(value)))
				# print 'in the key:' + str(key) + " : params: " + str(p.params[key])
				# print "key:\t" + str(key) + "\tparams:" + str(p.params)	
				tempExecParams[key] = []
				tempExecParams[key].append(value[p.params[key]])
				# print "tempExecParams: " + str(tempExecParams)
		self.randCnt = self.randCnt + 1
		# print "\tparams:" + str(tempExecParams)					
		p.execparm = tempExecParams


if __name__=="__main__":

	allHsiCode = ['2382', '19', '151', '1044']
	allStrategy = ['MovingMomentum']
	codeName = {'5': 'HSBCHoldings', '11': 'HangSengBank', '23': 'BankofEAsia', '388': 'HKEx', '939': 'CCB', '1299': 'AIA', '1398': 'ICBC', '2318': 'PingAn', '2388': 'BOCHongKong', '2628': 'ChinaLife', '3328': 'Bankcomm', '3988': 'BankofChina', '2': 'CLPHoldings', '3': 'HK&ChinaGas', '6': 'PowerAssets', '836': 'ChinaResPower', '1038': 'CKIHoldings', '12': 'HendersonLand', '16': 'SHKPpt', '17': 'NewWorldDev', '83': 'SinoLand', '101': 'HangLungPpt', '688': 'ChinaOverseas', '823': 'LinkREIT', '1109': 'ChinaResLand', '1113': 'CKAsset', '1997': 'WharfREIC', '2007': 'CountryGarden', '1': 'CKHHoldings', '19': 'SwirePacificA', '27': 'GalaxyEnt', '66': 'MTRCorporation', '144': 'ChinaMerPort', '151': 'WantWantChina', '175': 'GeelyAuto', '267': 'CITIC', '288': 'WHGroup', '386': 'SinopecCorp', '700': 'Tencent', '762': 'ChinaUnicom', '857': 'PetroChina', '883': 'CNOOC', '941': 'ChinaMobile', '992': 'LenovoGroup', '1044': 'HenganIntl', '1088': 'ChinaShenhua', '1928': 'SandsChinaLtd', '2018': 'AACTech', '2319': 'MengniuDairy', '2382': 'SunnyOptical'}

	pso = TimeVariantParticleSwarmOp()

	# pso.pso( "BollingerBandsStrategy")
		
	for strategy in allStrategy:
		fileObject = open(strategy+'Result', 'w+')
		for code in allHsiCode:	
			record = pso.pso( strategy, code)
			record = codeName.get(code) + '\t' + record
			fileObject.write(record)
		fileObject.close()	
