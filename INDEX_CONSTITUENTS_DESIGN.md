# 指数成分股数据表设计文档

## 概述

本文档描述了用于记录指数成分股信息的数据库表设计，支持历史变更追踪和时间点查询。

## 数据表结构

### 1. indexes 表（指数基本信息）

存储指数的基本信息。

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| id | INTEGER | 主键 | PRIMARY KEY, AUTO_INCREMENT |
| symbol | VARCHAR(32) | 指数代码（如 ^HSI, ^NDX） | UNIQUE, NOT NULL, INDEX |
| name | VARCHAR(255) | 指数名称 | NOT NULL |
| exchange | VARCHAR(64) | 交易所 | NULL |
| currency | VARCHAR(16) | 货币 | NULL |
| description | TEXT | 描述信息 | NULL |

**示例数据：**
```sql
INSERT INTO indexes (symbol, name, exchange, currency, description) VALUES
('^HSI', '恒生指数', 'HKEX', 'HKD', '香港恒生指数'),
('^NDX', '纳斯达克100指数', 'NASDAQ', 'USD', '纳斯达克100指数');
```

### 2. index_constituents 表（指数成分股关系）

存储指数与成分股的关系，支持历史变更追踪。

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| id | INTEGER | 主键 | PRIMARY KEY, AUTO_INCREMENT |
| index_id | INTEGER | 指数ID | FOREIGN KEY(indexes.id), NOT NULL, INDEX |
| symbol_id | INTEGER | 股票ID | FOREIGN KEY(symbols.id), NOT NULL, INDEX |
| symbol | VARCHAR(32) | 股票代码（冗余字段） | NOT NULL, INDEX |
| effective_date | DATE | 生效日期 | NOT NULL, INDEX |
| expiry_date | DATE | 失效日期 | NULL, INDEX |
| weight | FLOAT | 权重（可选） | NULL |
| notes | TEXT | 备注 | NULL |

**约束：**
- UNIQUE(index_id, symbol_id, effective_date) - 确保同一指数、同一股票、同一生效日期只有一条记录

**字段说明：**

- **effective_date（生效日期）**：股票加入指数的日期
- **expiry_date（失效日期）**：股票从指数中移除的日期
  - NULL 表示该股票仍在指数中
  - 有值表示该股票已被移除
- **weight（权重）**：某些指数会公布成分股权重，可选字段
- **notes（备注）**：记录变更原因、调整说明等信息

## 使用场景

### 场景1：查询当前成分股

查询某个指数在指定日期（或当前日期）的所有成分股：

```python
def get_current_constituents(session, index_symbol, as_of_date=None):
    if as_of_date is None:
        as_of_date = date.today()
    
    constituents = (
        session.query(IndexConstituent)
        .join(Index)
        .filter(
            Index.symbol == index_symbol,
            IndexConstituent.effective_date <= as_of_date,
            or_(
                IndexConstituent.expiry_date.is_(None),
                IndexConstituent.expiry_date > as_of_date,
            ),
        )
        .all()
    )
    return constituents
```

**SQL 示例：**
```sql
-- 查询恒生指数在 2023-12-31 的成分股
SELECT ic.symbol, ic.effective_date, ic.expiry_date, ic.weight
FROM index_constituents ic
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^HSI'
  AND ic.effective_date <= '2023-12-31'
  AND (ic.expiry_date IS NULL OR ic.expiry_date > '2023-12-31');
```

### 场景2：添加新成分股

当指数调整，新增成分股时：

```python
add_constituent(
    session,
    index_symbol="^HSI",
    stock_symbol="0700.HK",
    effective_date=date(2024, 1, 1),
    weight=10.5,
    notes="季度调整新增",
)
```

### 场景3：移除成分股

当成分股被移出指数时，设置失效日期：

```python
remove_constituent(
    session,
    index_symbol="^HSI",
    stock_symbol="0005.HK",
    expiry_date=date(2023, 12, 31),
    notes="季度调整移除",
)
```

### 场景4：查询历史变更

查询某个股票在指数中的历史记录：

```sql
-- 查询腾讯(0700.HK)在恒生指数中的历史
SELECT ic.effective_date, ic.expiry_date, ic.weight, ic.notes
FROM index_constituents ic
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^HSI'
  AND ic.symbol = '0700.HK'
ORDER BY ic.effective_date DESC;
```

### 场景5：统计指数成分股数量变化

```sql
-- 统计每个月末的成分股数量
SELECT 
    DATE_FORMAT(d.date, '%Y-%m') as month,
    COUNT(*) as constituent_count
FROM (
    SELECT LAST_DAY('2023-01-01') + INTERVAL n MONTH as date
    FROM (SELECT 0 as n UNION SELECT 1 UNION SELECT 2 ...) numbers
) d
JOIN index_constituents ic ON 
    ic.effective_date <= d.date AND
    (ic.expiry_date IS NULL OR ic.expiry_date > d.date)
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^HSI'
GROUP BY month
ORDER BY month;
```

## 数据获取方式

### 方式1：从数据源API获取

某些数据提供商（如 Bloomberg, Reuters）提供指数成分股的历史数据API，包括：
- 当前成分股列表
- 历史变更记录
- 生效日期和失效日期

### 方式2：从网页爬取

许多指数的官方网站或金融网站会公布成分股信息：
- 维基百科（如 NASDAQ-100）
- 交易所官网（如 HKEX）
- 金融数据网站（如 Yahoo Finance, Bloomberg）

**注意：** 大多数公开数据源只提供当前成分股，历史变更数据较难获取。

### 方式3：定期快照

如果无法获取历史数据，可以采用定期快照的方式：
1. 每天/每周/每月记录一次当前成分股
2. 通过对比前后快照，推断出变更
3. 自动填充 effective_date 和 expiry_date

**实现示例：**
```python
def snapshot_constituents(session, index_symbol, snapshot_date):
    """记录指定日期的成分股快照"""
    # 获取当前成分股列表（从API或爬虫）
    current_symbols = fetch_current_constituents(index_symbol)
    
    # 获取数据库中的当前成分股
    db_constituents = get_current_constituents(session, index_symbol, snapshot_date)
    db_symbols = {c.symbol for c in db_constituents}
    
    # 找出新增的股票
    new_symbols = set(current_symbols) - db_symbols
    for symbol in new_symbols:
        add_constituent(session, index_symbol, symbol, snapshot_date)
    
    # 找出移除的股票
    removed_symbols = db_symbols - set(current_symbols)
    for symbol in removed_symbols:
        remove_constituent(session, index_symbol, symbol, snapshot_date)
```

## 数据维护建议

1. **定期更新**：建议每天或每周运行一次快照脚本，及时捕获成分股变更
2. **数据验证**：定期验证数据完整性，确保没有遗漏的变更
3. **备注记录**：在 notes 字段中记录变更原因，便于后续分析
4. **权重更新**：如果使用权重字段，需要定期更新（某些指数每季度调整权重）

## 查询优化

为了提高查询性能，已在以下字段上创建索引：
- index_id
- symbol_id
- symbol
- effective_date
- expiry_date

对于频繁的时间点查询，可以考虑：
1. 使用物化视图缓存当前成分股
2. 添加复合索引：(index_id, effective_date, expiry_date)

## 迁移和使用

### 1. 创建表

```bash
python migrate_create_index_tables.py
```

### 2. 管理成分股数据

```bash
python manage_index_constituents.py
```

### 3. 在代码中使用

```python
from common.db import Index, IndexConstituent, get_session
from datetime import date

with get_session() as session:
    # 查询当前成分股
    constituents = get_current_constituents(session, "^HSI")
    
    # 查询历史某个时间点的成分股
    historical = get_current_constituents(session, "^HSI", date(2023, 1, 1))
```

## 扩展功能

未来可以考虑添加：
1. **成分股变更通知**：当检测到成分股变更时发送通知
2. **权重历史追踪**：如果权重经常变化，可以创建单独的权重历史表
3. **分类信息**：添加行业分类、市值分类等字段
4. **调整原因分类**：将 notes 字段标准化为预定义的调整原因代码

## 相关文件

- [`common/db.py`](common/db.py) - 数据模型定义
- [`migrate_create_index_tables.py`](migrate_create_index_tables.py) - 表创建脚本
- [`manage_index_constituents.py`](manage_index_constituents.py) - 管理示例脚本