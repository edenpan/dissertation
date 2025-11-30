# adj_close 数据获取修复说明

## 问题描述
用户反馈 `adj_close` 的值没有获取到。

## 问题分析
经过代码审查和测试，发现了两个主要问题：
1. **数据摄取问题**：`yfinance` 使用 `auto_adjust=True` 参数导致不返回 `Adj Close` 列
2. **股票代码格式问题**：策略代码使用简化格式（如 '5'），但数据库存储完整格式（如 '0005.HK'）

## 修复内容

### 1. 修复数据摄取中的 auto_adjust 参数 (data_pipeline/ingest.py)

**修改位置**: `_download_history()` 函数（第173-184行）

**问题**: 使用 `auto_adjust=True` 会导致 yfinance 不返回 `Adj Close` 列

**修改前**:
```python
data = yf.download(
    symbol,
    start=start,
    end=end_exclusive,
    interval="1d",
    auto_adjust=True,  # 这会导致没有 Adj Close 列
    progress=False,
    prepost=False,
    threads=False,
)
```

**修改后**:
```python
data = yf.download(
    symbol,
    start=start,
    end=end_exclusive,
    interval="1d",
    auto_adjust=False,  # 改为 False 以获取 Adj Close 列
    progress=False,
    prepost=False,
    threads=False,
)
```

### 2. 添加股票代码格式转换 (strategies/utils.py)

**修改位置**: 添加 `_normalize_symbol()` 函数，并在 `getStockData()` 和 `getStockDataWithTime()` 中使用

**问题**: 策略代码使用 '5' 格式，但数据库存储 '0005.HK' 格式

**新增函数**:
```python
def _normalize_symbol(symbol: str) -> str:
    """Normalize stock symbol to match database format.
    
    Converts Hong Kong stock codes like '5', '0005', '5.HK' to '0005.HK' format.
    Leaves other symbols unchanged.
    """
    symbol = symbol.strip()
    
    # If already in correct format (e.g., '0005.HK'), return as is
    if symbol.endswith('.HK'):
        return symbol
    
    # Check if it's a numeric Hong Kong stock code
    try:
        # Remove any leading zeros and convert to int to validate
        code_num = int(symbol)
        # Format as 4-digit code with .HK suffix
        return f"{code_num:04d}.HK"
    except ValueError:
        # Not a numeric code, return as is (e.g., 'AAPL', 'MSFT')
        return symbol
```

**修改后的函数**:
```python
def getStockData(symbol: str) -> pd.DataFrame:
    """Fetch the full price history for a ticker."""
    normalized_symbol = _normalize_symbol(symbol)
    return sqlUtil.getDaliyData(normalized_symbol)


def getStockDataWithTime(symbol: str, startTime: str | date, endTime: str | date) -> pd.DataFrame:
    """Fetch price history between two dates (inclusive)."""
    normalized_symbol = _normalize_symbol(symbol)
    start = _normalize_date(startTime)
    end = _normalize_date(endTime)
    return sqlUtil.getDaliyData(normalized_symbol, start=start, end=end)
```

### 3. 调整查询字段顺序 (crawler/util/sqlUtil.py)

**修改位置**: `_build_price_query()` 函数（第93-112行）

**修改前**:
```python
select(
    DailyPrice.traded_at.label("datetime"),
    DailyPrice.open,
    DailyPrice.close,  # close 在 high/low 之前
    DailyPrice.high,
    DailyPrice.low,
    DailyPrice.adj_close,
    DailyPrice.volume,
)
```

**修改后**:
```python
select(
    DailyPrice.traded_at.label("datetime"),
    DailyPrice.open,
    DailyPrice.high,    # 调整为标准 OHLC 顺序
    DailyPrice.low,
    DailyPrice.close,
    DailyPrice.adj_close,
    DailyPrice.volume,
)
```

## 数据流程说明

### 完整的 adj_close 数据流程：

1. **数据插入** (`insertPd()` 函数，第32-77行)
   - 接收包含 `adjclose` 列的 DataFrame
   - 将 `adjclose` 重命名为 `adj_close`
   - 存入数据库的 `daily_prices.adj_close` 字段

2. **数据查询** (`getDaliyData()` 函数，第80-90行)
   - 从数据库查询 `adj_close` 字段
   - 将 `adj_close` 重命名回 `adjclose`
   - **重要**: 如果 `adjclose` 为 NaN，自动用 `close` 值填充

3. **数据使用** (backtest.py)
   - 第43行: 买入时使用 `adjclose` 计算股票数量
   - 第49行: 卖出时使用 `adjclose` 计算资金
   - 第56行: 最后持仓时使用 `adjclose` 计算最终资金
   - 第69行: 计算买入持有策略的收益率

## 数据摄取

在使用之前，需要先摄取股票数据到数据库：

```bash
# 摄取单个股票（例如股票代码 5）
python3 ingest_stock_data.py 5

# 摄取所有恒生指数成分股
python3 ingest_stock_data.py
```

## 验证方法

### 1. 检查数据库中的股票代码
```bash
python3 check_db_symbols.py
```

该脚本会显示：
- 数据库中所有股票及其数据行数
- 验证特定股票代码的存在
- 显示样本数据（包括 adj_close）

### 2. 测试数据获取
```bash
python3 test_adj_close.py
```

该脚本会：
- 获取指定股票的历史数据
- 检查 `adjclose` 列是否存在
- 显示数据统计信息
- 比较 `adjclose` 和 `close` 的差异

### 3. 验证结果示例

成功获取数据后，应该看到类似输出：
```
正在获取股票 5 的数据...

数据形状: (846, 7)

列名: ['datetime', 'open', 'high', 'low', 'close', 'adjclose', 'volume']

✓ adjclose 列存在
adjclose 空值数量: 0

前5行数据:
    datetime   open   high    low  close  adjclose    volume
0 2013-07-15  84.55  85.25  84.35  85.10   43.5827   9055181
1 2013-07-16  85.35  85.45  84.65  85.05   43.5571   8289784
2 2013-07-17  85.10  85.65  85.05  85.50   43.7875   7604596
3 2013-07-18  85.95  86.00  85.65  85.70   43.8900   8567044
4 2013-07-19  87.20  87.20  86.35  86.70   44.4021  18925444

adjclose 统计信息:
count    846.000000
mean      38.737320
std        5.113267
min       27.383200
25%       35.361900
50%       39.740900
75%       43.015100
max       45.861700
Name: adjclose, dtype: float64

adjclose 和 close 的平均差异: 30.9935
adjclose 和 close 的最大差异: 43.6883
差异大于0.01的行数: 846 / 846
```

## 注意事项

1. **数据库连接**: 确保数据库配置正确，环境变量设置完整
2. **依赖包**: 如果遇到 `cryptography` 包缺失错误，需要安装：
   ```bash
   pip install cryptography
   ```
3. **数据完整性**: 如果数据库中的 `adj_close` 字段为 NULL，系统会自动使用 `close` 值作为后备

## 相关文件

### 修改的文件
- `data_pipeline/ingest.py`: 数据摄取管道（修复 auto_adjust 参数）
- `strategies/utils.py`: 策略工具函数（添加股票代码格式转换）
- `crawler/util/sqlUtil.py`: 数据库操作工具（调整查询字段顺序）

### 新增的文件
- `ingest_stock_data.py`: 数据摄取脚本
- `test_adj_close.py`: 数据获取测试脚本
- `check_db_symbols.py`: 数据库股票代码检查脚本
- `ADJ_CLOSE_FIX.md`: 本修复说明文档

### 其他相关文件
- `strategies/componentTradingRules/pso/backtest.py`: 回测框架
- `common/db.py`: 数据库模型定义