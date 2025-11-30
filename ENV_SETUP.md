# 环境变量配置指南

## 概述

本项目使用 `.env` 文件来管理敏感的数据库配置信息，避免将密码等信息提交到 Git 仓库。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

这会安装 `python-dotenv` 库，用于加载 `.env` 文件。

### 2. 创建 .env 文件

复制 `.env.example` 文件并重命名为 `.env`：

```bash
cp .env.example .env
```

### 3. 配置数据库连接

编辑 `.env` 文件，填入你的实际数据库配置：

```bash
# 数据库配置
DATA_DB_HOST=192.168.50.216
DATA_DB_PORT=3306
DATA_DB_USER=your_username
DATA_DB_PASSWORD=your_password
DATA_DB_NAME=stockdb
DATA_DB_CHARSET=utf8mb4
```

**重要提示：**
- ⚠️ **不要将 `.env` 文件提交到 Git**（已在 `.gitignore` 中配置）
- ✅ 只提交 `.env.example` 模板文件
- 🔒 `.env` 文件包含敏感信息，应妥善保管

## 配置说明

### 数据库配置项

| 环境变量 | 说明 | 默认值 | 示例 |
|---------|------|--------|------|
| `DATA_DB_HOST` | 数据库主机地址 | `localhost` | `192.168.50.216` |
| `DATA_DB_PORT` | 数据库端口 | `3306` | `3306` |
| `DATA_DB_USER` | 数据库用户名 | `root` | `eden` |
| `DATA_DB_PASSWORD` | 数据库密码 | `""` (空) | `your_password` |
| `DATA_DB_NAME` | 数据库名称 | `stockdb` | `stockdb` |
| `DATA_DB_CHARSET` | 数据库字符集 | `utf8mb4` | `utf8mb4` |

### 默认值说明

如果 `.env` 文件不存在或某个配置项未设置，系统会使用以下默认值：

- **HOST**: `localhost` - 本地数据库
- **PORT**: `3306` - MySQL 默认端口
- **USER**: `root` - MySQL 默认用户
- **PASSWORD**: `""` - 空密码（本地开发）
- **NAME**: `stockdb` - 数据库名称
- **CHARSET**: `utf8mb4` - 支持完整的 Unicode 字符集

## 使用示例

### 本地开发环境

```bash
# .env
DATA_DB_HOST=localhost
DATA_DB_PORT=3306
DATA_DB_USER=root
DATA_DB_PASSWORD=
DATA_DB_NAME=stockdb
DATA_DB_CHARSET=utf8mb4
```

### 生产环境

```bash
# .env
DATA_DB_HOST=192.168.50.216
DATA_DB_PORT=3306
DATA_DB_USER=prod_user
DATA_DB_PASSWORD=secure_password_here
DATA_DB_NAME=stockdb_prod
DATA_DB_CHARSET=utf8mb4
```

### Docker 环境

```bash
# .env
DATA_DB_HOST=mysql
DATA_DB_PORT=3306
DATA_DB_USER=docker_user
DATA_DB_PASSWORD=docker_password
DATA_DB_NAME=stockdb
DATA_DB_CHARSET=utf8mb4
```

## 验证配置

创建一个测试脚本来验证数据库连接：

```python
# test_db_connection.py
from sqlalchemy import text
from common.db import get_engine

try:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✓ 数据库连接成功!")
        print(f"  数据库: {engine.url.database}")
        print(f"  主机: {engine.url.host}:{engine.url.port}")
        print(f"  用户: {engine.url.username}")
except Exception as e:
    print(f"✗ 数据库连接失败: {e}")
```

运行测试：

```bash
python test_db_connection.py
```

## 故障排查

### 问题1：找不到 .env 文件

**错误信息：**
```
数据库连接失败: Access denied for user 'root'@'localhost'
```

**解决方法：**
1. 确认 `.env` 文件存在于项目根目录
2. 检查 `.env` 文件中的配置是否正确
3. 确认数据库用户名和密码是否正确

### 问题2：python-dotenv 未安装

**错误信息：**
```
ModuleNotFoundError: No module named 'dotenv'
```

**解决方法：**
```bash
pip install python-dotenv
# 或
pip install -r requirements.txt
```

### 问题3：数据库连接被拒绝

**错误信息：**
```
Can't connect to MySQL server on 'localhost'
```

**解决方法：**
1. 确认 MySQL 服务正在运行
2. 检查主机地址和端口是否正确
3. 确认防火墙设置允许连接

### 问题4：字符集问题

**错误信息：**
```
Incorrect string value: '\xF0\x9F...'
```

**解决方法：**
确保使用 `utf8mb4` 字符集：
```bash
DATA_DB_CHARSET=utf8mb4
```

## 团队协作

### 新成员加入项目

1. 克隆项目仓库
   ```bash
   git clone <repository_url>
   cd dissertation
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

3. 创建 `.env` 文件
   ```bash
   cp .env.example .env
   ```

4. 向团队管理员索取数据库配置信息

5. 编辑 `.env` 文件，填入配置

6. 测试连接
   ```bash
   python test_db_connection.py
   ```

### 更新配置模板

如果需要添加新的环境变量：

1. 更新 `.env.example` 文件
2. 更新本文档
3. 通知团队成员更新他们的 `.env` 文件
4. 提交 `.env.example` 的更改到 Git

## 安全建议

1. ✅ **永远不要提交 `.env` 文件到 Git**
2. ✅ 使用强密码
3. ✅ 定期更换数据库密码
4. ✅ 为不同环境使用不同的数据库用户
5. ✅ 限制数据库用户的权限
6. ✅ 在生产环境使用 SSL 连接
7. ❌ 不要在代码中硬编码密码
8. ❌ 不要在日志中输出密码

## 相关文件

- [`.env.example`](.env.example) - 环境变量模板文件
- [`.gitignore`](.gitignore) - Git 忽略规则（包含 `.env`）
- [`common/db.py`](common/db.py) - 数据库连接配置
- [`requirements.txt`](requirements.txt) - Python 依赖（包含 `python-dotenv`）