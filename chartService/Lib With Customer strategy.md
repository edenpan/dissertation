# Lib With Custom strategy

## The relate modules

### charting_libaray 
This is the TradingView libaray that we need to use to plot.  
The codes that need to be changed as fellows:

1. charting_library/charting_library/static/indicators.js  
	The js file used to create customIndicators.  
	**var symbol = "Indic#" + PineJS.Std.ticker(this._context) + "#MAC";**   Change MAC into any strategy name.  
	In the other part of the js, that can be changed to set the indicator's features. More can reference to the documents.
2. 	Add the customer Indicators as a widget into the html.Just  as the mytest.html.
The request for strategy:
GET /history?symbol=Indic#0005#MAC5&resolution=D&from=1499667633&to=1531808493


### python backend server
A mini flask app, that use to response the charting_libaray requests as the ChartServices.md mentioned.  
And a simple demo for the strategy, mac5 has been implement in the symbolHistory.py.
The file need to be change:

1. stockData/SymbolListInfo.py  
	**self.supportIndicator = ["MAC5"]** add the customer indicator name in here to return the symbol feature.
2. stockData/SymbolHistory.py
	
		#in these part to judge whether ask for history or for
		# the technical indicator data.
		if(self.symbolName.startswith("Indic#")):
			code = self.symbolName.split('#')[1]
			technical = self.symbolName.split('#')[2]
			techData = []
			#In here can add more custormer indicator
			if( technical == 'MAC5'):
				macData = mac(code)
				result["s"] = "ok"
				result["c"] = macData.get('m')
				result["t"] = macData.get('t')

			return result
		
	





	


		
 




