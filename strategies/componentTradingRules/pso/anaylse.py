for key in pso1.keys():
	if pso1[key][0] > pso2[key][0]:
		psoFinal[key] = pso1[key]
	else:
		psoFinal[key] = pso2[key]	
		
fileObject = open('PsoCombine', 'w+')	

for key in psoFinal.keys():
	record = str(key) + '\t' +str(psoFinal[key][2]) +  '\t' + str(psoFinal[key][1]) + '\t' + str(psoFinal[key][0]) + '\n'
	fileObject.write(record)


for key in psoRes.keys():
	psoRes[key].append(usuRes[key])	


fileObject = open('OutPsoUsuCompare', 'w+')		

for key in psoRes.keys():
	record = str(key) + '\t' +str(psoRes[key][0]) +  '\t' + str(psoRes[key][1]) + '\n'
	fileObject.write(record)

fileObject.close()	
