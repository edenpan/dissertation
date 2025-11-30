# coding: utf-8
import sys
sys.path.append('../')
import utils
import pandas as pd
import numpy as np
from BollingerBandsStrategy import BollingerBandsStrategy
from MovingAverage import MovingAverage
from RelativeStrengthIndex import RelativeStrengthIndex
from MacdHistogram import MacdHistogram

class CombinedStrategy:
    def __init__(self):
        self.strategyName = "CombinedStrategy"
        self.strategies = {
            'bb': BollingerBandsStrategy(),
            'ma': MovingAverage(),
            'rsi': RelativeStrengthIndex(),
            'macd': MacdHistogram()
        }

    def defaultParam(self):
        params = {}
        for name, strategy in self.strategies.items():
            strategy_params = strategy.defaultParam()
            for key, value in strategy_params.items():
                params[f"{name}_{key}"] = value
        return params

    def checkParams(self, **kwargs):
        for name, strategy in self.strategies.items():
            strategy_kwargs = {}
            for key, value in kwargs.items():
                if key.startswith(f"{name}_"):
                    strategy_kwargs[key[len(name)+1:]] = value
            if not strategy.checkParams(**strategy_kwargs):
                return False
        return True

    def parseparams(self, para):
        # This method is used to parse the column name back to parameters
        # Since we are combining strategies, the column name will be complex
        # For now, we can return a dummy dictionary or implement proper parsing if needed
        return {}

    def run(self, stockData, **kwargs):
        # Separate parameters for each strategy
        strategy_params = {name: {} for name in self.strategies}
        for key, value in kwargs.items():
            for name in self.strategies:
                if key.startswith(f"{name}_"):
                    strategy_params[name][key[len(name)+1:]] = value
        
        # Run each strategy
        results = {}
        valid_strategies = 0
        
        # We need to handle the case where run returns multiple columns
        # But in PSO context, we expect single parameter set
        
        combined_score = pd.Series(0.0, index=stockData['datetime'])
        
        final_col_name = ""
        
        for name, strategy in self.strategies.items():
            res, cnt = strategy.run(stockData, **strategy_params[name])
            if cnt > 0:
                # Assuming the first column is the result for the current parameters
                # In PSO, we usually pass one set of parameters, so there should be one column
                col = res.columns[0]
                if final_col_name:
                    final_col_name += "__"
                final_col_name += f"{name}_{col}"
                
                combined_score += res[col]
                valid_strategies += 1
        
        # Normalize score? Or just use majority vote logic (sum > 0 buy, sum < 0 sell)
        # The individual strategies return 1.0 for buy, -1.0 for sell, 0.0 for hold
        
        # If we want strict majority:
        # buy if sum > 0
        # sell if sum < 0
        
        final_res = pd.DataFrame(index=stockData['datetime'])
        final_res[final_col_name] = combined_score
        
        return final_res, 1

if __name__=="__main__":
    stockDataTrain = utils.getStockDataTrain("0005", True)
    cs = CombinedStrategy()
    # For testing, we pick first value of default params
    params = cs.defaultParam()
    test_params = {k: [v[0]] for k, v in params.items()}
    print(cs.run(stockDataTrain, **test_params))