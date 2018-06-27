from flask import Flask
import time
import json
from flask import request
from stockData.symbolInfo import SymbolHSIInfo
app = Flask(__name__)

@app.route('/')
def hello_test():
    return 'hello, test'

@app.route('/time')
def get_time():
    return str(int(time.time() * 1000))

@app.route('/config')
def get_config():
    config = DefConfig()
    s = json.dumps(config.__dict__)
    return s

@app.route('/symbols')
def get_symbols():
    symbol = request.args.get('symbol')
    symInfo = SymbolHSIInfo(symbol+'.hk')
    return json.dumps(symInfo.__dict__)

@app.route('/history')    
def get_history():
    symbol = request.args.get('symbol')
    dateFrom = request.args.get('from')
    dateTo = request.args.get('to')
    resolution = request.args.get('resolution')
    print symbol,dateFrom,dateTo,resolution
    history = SymbolHSIInfo(symbol+'.hk')
    return json.dumps(history.__dict__)


class DefConfig(object):
    def __init__(self):
        self.supports_search = True
        self.supports_group_request = False
        self.supported_resolutions = ['1', '5', '15', '30', '60', '1D', '1W', '1M']
        self.supports_marks = False
        self.supports_time = True


