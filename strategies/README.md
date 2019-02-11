# strategies

## How-To

    1. Write your own strategies or use the current strategies. For example,StochasticOscillatorStrategy.
    2. Running the PSO with :
        python pso.py strateName stockCode
        eg:
        python pso.py MovingMomentum 5
    Note: strateName is the file name that has implemented the strategy.
        stockCode is the code of the stocks. HSBC is 5.
    4. The interface that need implement to run the pso optimazition.
        run(self, stockData, **kwargs) this function used to implement the strategy. The stockData is the data that will be used to test the function and kwargs contains the parameters the strategy needs. This function should implement the logic of the strategy and give an execution result with stockData.  
        parseparms(self, para) this function used to define how to parse the para and get the running parameter of the strategy.  
        score(self, row) is the function that determines whether sell or buy with one day's indicator. This function will be used in the run function. 
        checkParams(self, **kwargs) being used to check if the parameter valid.
        defaultParam(self) the default parameter that can be used to run the strategy.

## Task List
1. [] Change to use standard log output
2. [] Adding more datasource, eg. Foreign Currency.
