from common.db import get_engine

try:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")
        print("✓ 数据库连接成功!")
        print(f"  数据库: {engine.url.database}")
        print(f"  主机: {engine.url.host}:{engine.url.port}")
except Exception as e:
    print(f"✗ 数据库连接失败: {e}")
