# 指数成分股同步使用指南

## 概述

本文档说明如何使用 [`sync_index_constituents.py`](sync_index_constituents.py) 脚本同步指数成分股数据。

## 功能特性

✅ **自动比对差异**：对比数据源和数据库中的成分股，自动识别新增和移除的股票
✅ **时间追踪**：新增股票设置 `effective_date`，移除股票设置 `expiry_date`
✅ **权重同步**：自动获取和更新成分股权重信息（如果数据源提供）
✅ **数据来源标记**：记录数据来源（如 `wiki`、`bloomberg`）
✅ **时间戳记录**：自动记录 `created_at` 和 `updated_at`
✅ **幂等性**：可重复运行，不会产生重复数据

## 数据表结构

### index_constituents 表新增字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| source | VARCHAR(32) | 数据来源 | `wiki`, `bloomberg`, `manual` |
| created_at | DATETIME | 创建时间 | `2024-01-15 10:30:00` |
| updated_at | DATETIME | 更新时间 | `2024-01-15 10:30:00` |

## 使用步骤

### 1. 首次使用：创建表和迁移

如果是首次使用，需要先创建表：

```bash
# 创建 indexes 和 index_constituents 表
python migrate_create_index_tables.py
```

如果表已存在但缺少新字段，运行迁移脚本：

```bash
# 添加 source, created_at, updated_at 字段
python migrate_add_constituent_fields.py
```

### 2. 同步指数成分股

```bash
# 同步 NASDAQ-100 指数
python sync_index_constituents.py nasdaq100

# 或使用简写
python sync_index_constituents.py ndx
```

### 3. 查看同步结果

脚本会输出详细的同步信息：

```
============================================================
开始同步指数: ^NDX (NASDAQ-100)
============================================================

✓ 指数已存在: ^NDX - NASDAQ-100

从数据源获取成分股列表...
✓ 获取到 101 只成分股
✓ 数据库中当前有 100 只成分股

差异分析:
  - 新增: 2 只
  - 移除: 1 只
  - 未变: 99 只

处理新增成分股:
  + NVDA: 生效日期 = 2024-01-15, 权重 = 8.5%
  + TSLA: 生效日期 = 2024-01-15, 权重 = 3.2%

处理移除成分股:
  - FB: 失效日期 = 2024-01-15, 权重 = 2.1%

检查权重更新:
  ~ AAPL: 权重 10.5% -> 11.2%
  ~ MSFT: 权重 9.8% -> 10.1%

============================================================
同步完成!
============================================================
统计信息:
  - 最新成分股数量: 101
  - 数据库原有数量: 100
  - 新增: 2
  - 移除: 1
  - 未变: 99
  - 权重更新: 2
  - 同步日期: 2024-01-15
  - 数据来源: wiki
```

## 同步逻辑说明

### 新增成分股

当检测到数据源中有新股票时：

1. 在 `symbols` 表中创建股票记录（如果不存在）
2. 在 `index_constituents` 表中创建新记录：
   - `effective_date` = 当天日期
   - `expiry_date` = NULL（表示仍在指数中）
   - `source` = 数据来源（如 `wiki`）
   - `created_at` = 当前时间

**示例：**
```sql
INSERT INTO index_constituents (
    index_id, symbol_id, symbol,
    effective_date, expiry_date, weight,
    source, created_at, updated_at
) VALUES (
    1, 123, 'NVDA',
    '2024-01-15', NULL, 8.5,
    'wiki', NOW(), NOW()
);
```

### 移除成分股

当检测到数据库中的股票不在数据源中时：

1. 查找该股票当前有效的记录（`expiry_date` 为 NULL 或未来日期）
2. 设置 `expiry_date` = 当天日期
3. 更新 `updated_at` = 当前时间

**示例：**
```sql
UPDATE index_constituents
SET expiry_date = '2024-01-15',
    updated_at = NOW()
WHERE index_id = 1
  AND symbol = 'FB'
  AND (expiry_date IS NULL OR expiry_date > '2024-01-15');
```

### 未变化的成分股

对于既在数据源又在数据库中的股票：

1. 检查权重是否有变化
2. 如果权重变化，更新 `weight` 字段和 `updated_at` 时间
3. 如果权重未变化，不做任何操作

**示例：**
```sql
UPDATE index_constituents
SET weight = 11.2,
    updated_at = NOW()
WHERE index_id = 1
  AND symbol = 'AAPL'
  AND (expiry_date IS NULL OR expiry_date > CURDATE());
```

## 数据来源（Source）

当前支持的数据来源标识：

| 标识 | 说明 | 数据源 |
|------|------|--------|
| `wiki` | 维基百科 | https://en.wikipedia.org/wiki/NASDAQ-100 |
| `manual` | 手动添加 | 通过脚本或 SQL 手动添加 |
| `bloomberg` | 彭博终端 | （未来支持） |
| `reuters` | 路透社 | （未来支持） |

## 定期同步建议

### 方式一：Cron 定时任务

在 Linux/macOS 上，可以使用 cron 定期运行：

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2 点同步 NASDAQ-100
0 2 * * * cd /path/to/project && /path/to/python sync_index_constituents.py nasdaq100 >> /var/log/sync_nasdaq100.log 2>&1
```

### 方式二：Python 调度器

使用 `schedule` 库：

```python
import schedule
import time
from sync_index_constituents import sync_constituents
from common.db import get_session

def job():
    with get_session() as session:
        sync_constituents(
            session,
            index_symbol="^NDX",
            index_name="NASDAQ-100",
            exchange="NASDAQ",
            currency="USD",
            source_key="nasdaq100",
        )

# 每天凌晨 2 点运行
schedule.every().day.at("02:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 方式三：手动运行

在需要时手动运行脚本：

```bash
python sync_index_constituents.py nasdaq100
```

## 查询示例

### 查询当前成分股

```sql
SELECT 
    ic.symbol,
    s.full_name,
    ic.effective_date,
    ic.source,
    ic.created_at
FROM index_constituents ic
JOIN symbols s ON ic.symbol_id = s.id
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
  AND ic.effective_date <= CURDATE()
  AND (ic.expiry_date IS NULL OR ic.expiry_date > CURDATE())
ORDER BY ic.symbol;
```

### 查询历史变更

```sql
-- 查询最近 30 天的变更
SELECT 
    ic.symbol,
    s.full_name,
    ic.effective_date,
    ic.expiry_date,
    ic.source,
    CASE 
        WHEN ic.expiry_date IS NULL THEN '当前成分股'
        WHEN ic.expiry_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN '最近移除'
        ELSE '历史成分股'
    END as status
FROM index_constituents ic
JOIN symbols s ON ic.symbol_id = s.id
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
  AND (
    ic.effective_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    OR ic.expiry_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    OR ic.expiry_date IS NULL
  )
ORDER BY ic.effective_date DESC, ic.symbol;
```

### 统计成分股数量变化

```sql
-- 按月统计成分股数量
SELECT 
    DATE_FORMAT(d.date, '%Y-%m') as month,
    COUNT(DISTINCT ic.symbol) as constituent_count
FROM (
    SELECT DATE_ADD('2023-01-01', INTERVAL n MONTH) as date
    FROM (
        SELECT 0 as n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 
        UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7
        UNION SELECT 8 UNION SELECT 9 UNION SELECT 10 UNION SELECT 11
    ) numbers
) d
JOIN index_constituents ic ON 
    ic.effective_date <= LAST_DAY(d.date) AND
    (ic.expiry_date IS NULL OR ic.expiry_date > LAST_DAY(d.date))
JOIN indexes i ON ic.index_id = i.id
WHERE i.symbol = '^NDX'
GROUP BY month
ORDER BY month;
```

## 扩展其他指数

要支持其他指数（如恒生指数），需要：

### 1. 在 [`data_pipeline/constituents.py`](data_pipeline/constituents.py) 中添加加载函数

```python
def _load_hsi() -> List[SymbolConfig]:
    """加载恒生指数成分股"""
    url = "https://www.hsi.com.hk/eng/indexes/all-indexes/hsi"
    # 实现爬取逻辑
    ...
    return configs

# 注册到加载器
_INDEX_LOADERS["hsi"] = _load_hsi
_INDEX_LOADERS["^hsi"] = _load_hsi
```

### 2. 在 [`sync_index_constituents.py`](sync_index_constituents.py) 中添加配置

```python
INDEX_CONFIGS = {
    # ... 现有配置 ...
    "hsi": {
        "symbol": "^HSI",
        "name": "恒生指数",
        "exchange": "HKEX",
        "currency": "HKD",
    },
}

SOURCE_MAP = {
    # ... 现有映射 ...
    "hsi": "hkex",  # 或其他数据源标识
}
```

### 3. 运行同步

```bash
python sync_index_constituents.py hsi
```

## 故障排查

### 问题1：表不存在

**错误信息：**
```
✗ index_constituents 表不存在
```

**解决方法：**
```bash
python migrate_create_index_tables.py
```

### 问题2：字段不存在

**错误信息：**
```
Unknown column 'source' in 'field list'
```

**解决方法：**
```bash
python migrate_add_constituent_fields.py
```

### 问题3：网络连接失败

**错误信息：**
```
Failed to download NASDAQ-100 constituents: ...
```

**解决方法：**
- 检查网络连接
- 确认可以访问维基百科
- 如果在中国大陆，可能需要使用代理

### 问题4：数据库连接失败

**错误信息：**
```
Can't connect to MySQL server
```

**解决方法：**
- 检查数据库配置（[`common/db.py`](common/db.py:29-34)）
- 确认数据库服务正在运行
- 检查用户名和密码是否正确

## 相关文件

- [`sync_index_constituents.py`](sync_index_constituents.py) - 同步脚本
- [`common/db.py`](common/db.py) - 数据模型定义
- [`data_pipeline/constituents.py`](data_pipeline/constituents.py) - 成分股加载器
- [`migrate_create_index_tables.py`](migrate_create_index_tables.py) - 表创建脚本
- [`migrate_add_constituent_fields.py`](migrate_add_constituent_fields.py) - 字段迁移脚本
- [`INDEX_CONSTITUENTS_DESIGN.md`](INDEX_CONSTITUENTS_DESIGN.md) - 设计文档