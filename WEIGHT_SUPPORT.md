# 指数成分股权重支持说明

## 概述

同步脚本现已支持自动获取和更新指数成分股的权重信息。

## 功能特性

### 1. 自动获取权重

从数据源（如维基百科）获取成分股时，如果表格中包含权重列（`Weight` 或 `Weighting`），会自动解析并保存。

**支持的格式：**
- 百分比格式：`10.5%`
- 数字格式：`10.5`

### 2. 新增成分股时保存权重

```python
# 示例输出
处理新增成分股:
  + NVDA: 生效日期 = 2024-01-15, 权重 = 8.5%
  + TSLA: 生效日期 = 2024-01-15, 权重 = 3.2%
```

### 3. 自动更新权重变化

对于已存在的成分股，如果权重发生变化，会自动更新：

```python
# 示例输出
检查权重更新:
  ~ AAPL: 权重 10.5% -> 11.2%
  ~ MSFT: 权重 9.8% -> 10.1%
```

### 4. 移除时记录权重

```python
# 示例输出
处理移除成分股:
  - FB: 失效日期 = 2024-01-15, 权重 = 2.1%
```

## 数据模型

### SymbolConfig 扩展

在 [`data_pipeline/ingest.py`](data_pipeline/ingest.py:20-39) 中，`SymbolConfig` 类新增了 `weight` 字段：

```python
@dataclass(frozen=True)
class SymbolConfig:
    symbol: str
    full_name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    weight: float | None = None  # 新增：权重字段
```

### IndexConstituent 表

`index_constituents` 表中的 `weight` 字段用于存储权重：

```sql
CREATE TABLE index_constituents (
    ...
    weight FLOAT NULL,  -- 权重（百分比，如 10.5 表示 10.5%）
    ...
);
```

## 使用示例

### 查询按权重排序的成分股

```sql
SELECT 
    ic.symbol,
    s.full_name,
    ic.weight,
    ic.effective_date
FROM index_constituents ic
JOIN symbols s ON ic.symbol_id = s.id
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
  AND ic.effective_date <= CURDATE()
  AND (ic.expiry_date IS NULL OR ic.expiry_date > CURDATE())
  AND ic.weight IS NOT NULL
ORDER BY ic.weight DESC;
```

### 查询权重最大的前10只股票

```sql
SELECT 
    ic.symbol,
    s.full_name,
    ic.weight
FROM index_constituents ic
JOIN symbols s ON ic.symbol_id = s.id
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
  AND ic.effective_date <= CURDATE()
  AND (ic.expiry_date IS NULL OR ic.expiry_date > CURDATE())
  AND ic.weight IS NOT NULL
ORDER BY ic.weight DESC
LIMIT 10;
```

### 计算权重总和

```sql
SELECT 
    SUM(ic.weight) as total_weight
FROM index_constituents ic
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
  AND ic.effective_date <= CURDATE()
  AND (ic.expiry_date IS NULL OR ic.expiry_date > CURDATE())
  AND ic.weight IS NOT NULL;
```

### 查询权重变化历史

```sql
SELECT 
    ic.symbol,
    ic.weight,
    ic.effective_date,
    ic.expiry_date,
    ic.updated_at
FROM index_constituents ic
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
  AND ic.symbol = 'AAPL'
ORDER BY ic.effective_date DESC;
```

## Python 代码示例

### 获取带权重的成分股

```python
from common.db import get_session, Index, IndexConstituent
from datetime import date

with get_session() as session:
    # 查询当前成分股及权重
    constituents = (
        session.query(IndexConstituent)
        .join(Index)
        .filter(
            Index.symbol == "^NDX",
            IndexConstituent.effective_date <= date.today(),
            (IndexConstituent.expiry_date.is_(None) | 
             (IndexConstituent.expiry_date > date.today()))
        )
        .order_by(IndexConstituent.weight.desc())
        .all()
    )
    
    for c in constituents:
        if c.weight:
            print(f"{c.symbol}: {c.weight}%")
        else:
            print(f"{c.symbol}: 权重未知")
```

### 计算投资组合

```python
from common.db import get_session, Index, IndexConstituent
from datetime import date

def calculate_portfolio(index_symbol: str, total_amount: float):
    """根据指数权重计算投资组合"""
    with get_session() as session:
        constituents = (
            session.query(IndexConstituent)
            .join(Index)
            .filter(
                Index.symbol == index_symbol,
                IndexConstituent.effective_date <= date.today(),
                (IndexConstituent.expiry_date.is_(None) | 
                 (IndexConstituent.expiry_date > date.today())),
                IndexConstituent.weight.isnot(None)
            )
            .all()
        )
        
        total_weight = sum(c.weight for c in constituents)
        
        portfolio = []
        for c in constituents:
            allocation = (c.weight / total_weight) * total_amount
            portfolio.append({
                "symbol": c.symbol,
                "weight": c.weight,
                "allocation": allocation
            })
        
        return portfolio

# 使用示例
portfolio = calculate_portfolio("^NDX", 100000)
for item in portfolio:
    print(f"{item['symbol']}: ${item['allocation']:.2f} ({item['weight']}%)")
```

## 数据源支持情况

| 指数 | 数据源 | 权重支持 | 说明 |
|------|--------|----------|------|
| NASDAQ-100 | 维基百科 | ⚠️ 部分支持 | 维基百科表格可能不包含权重列 |
| S&P 500 | 待实现 | ❌ | 需要实现加载器 |
| 恒生指数 | 待实现 | ❌ | 需要实现加载器 |

**注意：** 维基百科的 NASDAQ-100 页面通常不包含权重信息。如需获取准确的权重数据，建议：

1. 使用专业数据提供商（如 Bloomberg, Reuters）
2. 从交易所官网获取
3. 使用金融数据 API（如 Alpha Vantage, IEX Cloud）

## 扩展其他数据源

如果要从其他数据源获取权重，可以在 [`data_pipeline/constituents.py`](data_pipeline/constituents.py) 中添加新的加载函数：

```python
def _load_sp500_with_weights() -> List[SymbolConfig]:
    """从数据源加载 S&P 500 成分股及权重"""
    # 实现获取逻辑
    configs = []
    
    # 示例：从 API 获取
    data = fetch_sp500_data()  # 自定义函数
    
    for item in data:
        configs.append(
            SymbolConfig(
                symbol=item['ticker'],
                full_name=item['name'],
                exchange="NYSE",
                currency="USD",
                weight=item['weight'],  # 权重信息
            )
        )
    
    return configs

# 注册加载器
_INDEX_LOADERS["sp500"] = _load_sp500_with_weights
```

## 注意事项

1. **权重单位**：权重以百分比形式存储（如 10.5 表示 10.5%）
2. **权重总和**：某些指数的权重总和可能不等于 100%（如市值加权指数会定期调整）
3. **NULL 值**：如果数据源不提供权重，`weight` 字段为 NULL
4. **权重更新频率**：建议定期运行同步脚本以获取最新权重

## 相关文件

- [`data_pipeline/ingest.py`](data_pipeline/ingest.py:20-39) - SymbolConfig 定义
- [`data_pipeline/constituents.py`](data_pipeline/constituents.py:28-78) - 成分股加载器
- [`sync_index_constituents.py`](sync_index_constituents.py) - 同步脚本
- [`common/db.py`](common/db.py:115-175) - 数据模型