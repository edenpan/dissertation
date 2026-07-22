# 拷到 ~/.zipline/extension.py 用(zipline CLI / run_algorithm 会自动加载该文件注册 bundle)
import sys
sys.path.insert(0, "/home/eden/code/altas-quant/dissertation")
from zipline_lab.bundle_stockdb import (
    register_stockdb_bundle,
    register_stockdb_hk_bundle,
)
register_stockdb_bundle()       # 美股 bundle `stockdb`(XNYS)
register_stockdb_hk_bundle()    # 港股 bundle `stockdb-hk`(XHKG)
