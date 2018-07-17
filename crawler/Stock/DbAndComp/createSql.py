
#create  sql table file,fname1 :table list, fname2 : create sql merge them Together
def createSql(fname1, fname2):
	f1 = open(fname1,"r");
	f2 = open(fname2,"r");
	s1 = f1.read()
	s2 = f2.read()
	a1 = s2.split('\n')
	s = ""
	for a in a1:
	    s += a + '\n' + s1
	fo = open("test.txt", "w")
	fo.close()
	f1.close()
	f2.close()
	
