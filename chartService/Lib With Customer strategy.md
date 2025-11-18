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
A mini Flask app responds to the charting library requests described in `ChartServices.md`.  
Custom indicator endpoints now live inside `chart_service/services/history.py`. The `HistoryService.fetch` method already understands symbols in the form `Indic#<symbol>#<indicator>` and ships with MAC5 and Bollinger Bands examples.

To expose new indicators:

1. Extend the logic in `HistoryService._build_indicator_payload` (and supporting helpers) to calculate the indicator.
2. Add the indicator name to the front-end widget (e.g. `Indic#AAPL#MyIndicator`).
3. Optionally enrich the discovery experience by declaring the synthetic symbol in a custom configuration file referenced by `CHART_SERVICE_CONFIG`.
	





	


		
 



