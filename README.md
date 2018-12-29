# dissertation

## chartService
The backend of the chartView service.  
And the APIs that need to be implemented to run the TradingView Libaray are described as [here](https://github.com/edenpan/dissertation/blob/master/chartService/ChartServices.md).  
The [python](https://github.com/edenpan/dissertation/tree/master/chartService/python) directory is the runnable backend which making use of Flask to implement the APIs to provide the chart data.
Running this Flask web service(Python2.7):

    pip install -r requirements.txt
    export FLASK_APP='miniapp'
    flask run

To run the TradingView lib, there still need a nodejs project.

## crawler
The data crawler part.  
Basically to analysis the website and crawl the financial data.  
The Stock/history/yqd.py is used to get the daily stock data from yahoo and store the data into local postgresql database.  

## strategies
In this directory, there are a backtest framework and a pso parameter optimaziation and several implemented indicators.  




    