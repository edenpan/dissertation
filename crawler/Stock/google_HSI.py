# coding: utf-8
# author: chenfei
# usage: python google_finance_HSI.py
from lxml import html  
import requests
import json
import argparse
from collections import OrderedDict
from time import sleep
import pandas as pd
from datetime import datetime
import os

import sys
sys.path.insert(0,  '../util')
import common

def get_price(code):
   
    url = "https://www.google.com/finance?q=HKG:%s"%(code)

    response = requests.get(url,headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36"})
    parser = html.fromstring(response.text)

    summary_data = OrderedDict()

    u_time = str(datetime.now())[0:10]
    summary_data.update({'Date':u_time})
    summary_data.update({'Symbol':code})
    quote = parser.xpath('//div[contains(@id,"entity-summary")]/div[1]/g-card-section[1]/div/g-card-section/div/span[1]//text()')
    
    if len(quote) > 0:
    	summary_data.update({'Nominal price' : str(quote[0]).strip()})
    else:
        summary_data.update({'Nominal price' : '-'})

    price = parser.xpath('//div[contains(@id,"entity-summary")]/div[1]/div[1]/g-card-section[2]/div[1]/div[1]//td//text()')
    headers = ['Open', 'High', 'Low', 'Mkt cap', 'P/E ratio', 'Div yield', 'Prev close', '52-wk high', '52-wk low']

    summary_data.update({headers[0] : str(price[1]).strip()})
    summary_data.update({headers[1] : str(price[3]).strip()})
    summary_data.update({headers[2] : str(price[5]).strip()})
    summary_data.update({headers[3] : str(price[7]).strip()})
    summary_data.update({headers[4] : str(price[9]).strip()})
    summary_data.update({headers[5] : str(price[11]).strip()})
    summary_data.update({headers[6] : str(price[13]).strip()})
    summary_data.update({headers[7] : str(price[15]).strip()})
    summary_data.update({headers[8] : str(price[17]).strip()})
    return summary_data

if __name__=="__main__":
    
    index = commom.get_index()
    HSI_price_data = pd.DataFrame()
    f_data = get_price(index[0])
    cols = f_data.keys()

    for code in index:
    	# if code == '6098':
        #    continue
        summary_data = get_price(code)
        print summary_data
        price_data = pd.DataFrame.from_dict(summary_data, orient='index').T       
        HSI_price_data = pd.concat([HSI_price_data, price_data], sort=True)   
    
    u_time = str(datetime.now())[0:10]
    if not os.path.exists('data/google/'):
        os.makedirs('data/google/')

    file_name = 'data/google' + '/HSI_google_' + u_time
    HSI_price_data.to_csv(file_name + '.csv', sep=',', na_rep='N/A', columns=cols, index=False)




