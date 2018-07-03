HK Market Grabbers
=
A series of grabbers to scrape market data from different sources, for one stock or a list of stocks (like HSI).        
---
Notes:      
1. The code is based on python 2.7, although python 3.X is better to handle encoding problem.        
2. Please avoid non-business days or market-opening hours to run the scripts.        
2. All missing values after scraping are replaced with N/A, except fot Google finance with '-'.       
3. For one stock, please use its 4-digits code as input.     
4. Fox Heng Seng index, components code is from Bloomberg.       
5. Python Requests and LXML are needed. You can use pip or conda to install them.
6. Python Pandas should be >= 0.23.


Google finance
-
To scrape google finance market data, run google_finance_market.py in your terminal:   
`python google_finance_market.py 0700`      
To further get HSI components market data, simply run google_finance_HSI.py:     
`python google_finance_HSI.py`

Example output:  
    
Date|Symbol|Nominal price|Open|High|Low|Mkt cap|P/E ratio|Div yield|Prev close
:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:
2018/6/5|700|418.6|418.8|418.8|415.4|3.98T|40.67|0.21%|415      


Yahoo finance
-
To scrape yahoo finance market data, run yahoo_finance_market.py in your terminal:   
`python yahoo_finance_market.py 0700`       
To further get HSI components market data, simply run yahoo_finance_HSI.py:     
`python yahoo_finance_HSI.py`

Example output:
        
Date|Symbol|Nominal price|Previous Close|Open|Bid|Ask
:-:|:-:|:-:|:-:|:-:|:-:|:-:
2018/6/5|700|419.6|415|418.8|419.400 x 0|419.600 x 0


Etnet
-
To scrape etnet finance market data for one stock, run etnet_finance_market.py in your terminal:   
`python etnet_finance_market.py 0700`       
To further get HSI components market data, simply run etnet_finance_HSI.py:     
`python etnet_finance_HSI.py` 
        
Example output:

Date|Symbol|Nominal price|High|Share Tr|Prev Close|1 Month High|MKT Cap|Low|Turnover|Open
:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:
2018/6/5|700|419.6|420|19.045M|415|423.32|3,944.030B|415.4|7.962B|418.8
       
       
Etnet Advisory
-
To scrape advisory data for one stock from etnet, run etnet_finance_advisory.py in your terminal:
`python etnet_finance_advisory.py 0700`       


HKEX
-
To scrape HKEX market data, run hkex_finance.py in your terminal:   
`python hkex_finance.py 0700`       
To further get HSI components market data, simply run hkex_HSI.py:          
`python hkex_HSI.py` 

Example output:
        
Date|Symbol|Nominal Price|Prev close|Open|Turnover|Volume|Mkt cap|Bid|Ask|EPS(RMB)
:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:
2018/6/5|700|419.4|415|418.8|6.84B|16.37M|3,985.84B|419.4|419.6|7.5986


Quandl
-
To use Quandl API, please install Quandl package:       
`conda install quandl` or `pip install quandl`      
then run quandl_finance.py in your terminal:      
`python quandl_finance.py 0700 2018-06-05 --days 5`         
days is optional parameter, which means the data horizon you needs (up to 4 years). It will skip non-business day.

Example output:
        
Date|Symbol|Nominal Price|Net Change|Change(%)|Bid|Ask|P/E(x)|High|Low|Previous Close
:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:
2018/5/31|700|399.2|N/A|N/A|399.2|399.4|N/A|401.8|395.2|395	
2018/6/1|700|404|N/A|N/A|403.8|404|N/A|404|398.2|399.2
2018/6/4|700|415|N/A|N/A|414.8|415|N/A|415|408.8|404

Bloomberg
-
To get HSI components market data, simply run bloomberg_HSI.py:          
`python bloomberg_HSI.py`





