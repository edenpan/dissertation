# APIs Description

## Services

name	|	Description
------------- | -------------
time	| provide server time
config | the chart basic config
symbols | current support symbols
history | trading data
search	| return search result


## Get

###/time

	GET 	/time
	1530001150613


### /search

	GET 	/search
	[{"symbol":"AAPL","full_name":"Apple Inc.","description":"Apple Inc.","exchange":"NASDAQ","ticker":"AAPL","type":"stock"},
	{"symbol":"MSFT","full_name":"Microsoft Corporation","description":"Microsoft Corporation","exchange":"NASDAQ","ticker":"MSFT","type":"stock"}]

### /config

	GET /config
	{
	  "supports_search": true,
	  "supports_group_request": false,
	  "supported_resolutions": [
	    "1",
	    "5",
	    "15",
	    "30",
	    "60",
	    "1D",
	    "1W",
	    "1M"
	  ],
	  "supports_marks": false,
	  "supports_time": true
	}
	
### /symbols?symbol=<symbol>	

	GET /symbols?symbol=<symbol>	
	
	{
	  "name": "AAPL",
	  "full_name": "Apple Inc.",
	  "ticker": "AAPL",
	  "description": "Apple Inc.",
	  "type": "stock",
	  "session": "0930-1600",
	  "exchange": "NASDAQ",
	  "listed_exchange": "NASDAQ",
	  "timezone": "America/New_York",
	  "pricescale": 100,
	  "minmov": 1,
	  "has_intraday": true,
	  "supported_resolutions": [
	    "1",
	    "5",
	    "15",
	    "30",
	    "60",
	    "1D"
	  ],
	  "has_daily": true,
	  "has_weekly_and_monthly": true,
	  "has_no_volume": false,
	  "currency_code": "USD"
	}
	
### /history?symbol=AAPL

	GET /history?symbol=AAPL
		{
	  "s": "ok",
	  "t": [
	    1528335000000,
	    1528335060000,
	    1528335120000,
	    1528335180000,
	  ],
	  "c": [
	    429.4,
	    429.2,
	    429.8,
	    430
	  ],
	  "o": [
	    431.2,
	    429.8,
	    429.2,
	    429.8
	  ],
	  "l": [
	    429.4,
	    429,
	    429,
	    429.6
	  ],
	  "h": [
	    431.6,
	    431,
	    430,
	    430.6
	  ],
	  "v": [
	    219700,
	    779000,
	    186900,
	    499600
	   ]
	}	
	
### /search

	GET /search

	[
	  {
	    "symbol": "AAPL",
	    "full_name": "Apple Inc.",
	    "description": "Apple Inc.",
	    "exchange": "NASDAQ",
	    "ticker": "AAPL",
	    "type": "stock"
	  },
	  {
	    "symbol": "MSFT",
	    "full_name": "Microsoft Corporation",
	    "description": "Microsoft Corporation",
	    "exchange": "NASDAQ",
	    "ticker": "MSFT",
	    "type": "stock"
	  }
	  ...
	]	
		
	

