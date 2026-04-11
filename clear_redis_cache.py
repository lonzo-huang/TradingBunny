#!/usr/bin/env python3
"""
清除 Nautilus Trader Redis 缓存脚本
"""
import asyncio
import os
import sys
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
project_root = Path(__file__).parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"✅ 加载环境变量: {env_file}")


def clear_redis_cache_sync():
    """同步清除 Redis 缓存"""
    try:
        import redis
        
        # 从环境变量获取 Redis 配置
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        print(f"🔌 连接到 Redis: {redis_host}:{redis_port}/{redis_db}")
        
        # 创建 Redis 连接
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password if redis_password else None,
            decode_responses=True
        )
        
        # 测试连接
        r.ping()
        print("✅ Redis 连接成功")
        
        # 获取所有 Nautilus 相关的 key
        # Nautilus 通常使用 "nautilus" 或 trader_id 作为前缀
        trader_id = os.getenv("TRADER_ID", "POLYMARKET-001")
        
        # 查找所有相关的 keys
        patterns = [
            f"{trader_id}:*",
            "nautilus:*",
            "*positions*",
            "*orders*",
            "*trades*",
        ]
        
        all_keys = []
        for pattern in patterns:
            keys = r.keys(pattern)
            all_keys.extend(keys)
        
        # 去重
        all_keys = list(set(all_keys))
        
        if not all_keys:
            print("ℹ️ 没有找到任何缓存数据")
            return
        
        print(f"🗑️  找到 {len(all_keys)} 个缓存 key:")
        for key in sorted(all_keys)[:20]:  # 只显示前20个
            print(f"   - {key}")
        if len(all_keys) > 20:
            print(f"   ... 还有 {len(all_keys) - 20} 个")
        
        # 确认删除
        response = input(f"\n⚠️  确定要删除这 {len(all_keys)} 个 key 吗? (yes/no): ")
        if response.lower() != "yes":
            print("❌ 已取消")
            return
        
        # 删除 keys
        deleted = r.delete(*all_keys)
        print(f"✅ 已删除 {deleted} 个 key")
        
        # 刷新所有数据
        r.flushdb()
        print("✅ 已执行 FLUSHDB (清除当前数据库)")
        
    except ImportError:
        print("❌ 未安装 redis 库，尝试安装: pip install redis")
        sys.exit(1)
    except redis.ConnectionError as e:
        print(f"❌ Redis 连接失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def clear_redis_cache_async():
    """异步清除 Redis 缓存（如果使用 aioredis）"""
    try:
        import aioredis
        
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))
        
        print(f"🔌 连接到 Redis (async): {redis_host}:{redis_port}/{redis_db}")
        
        r = await aioredis.create_redis_pool(
            f"redis://{redis_host}:{redis_port}/{redis_db}"
        )
        
        await r.flushdb()
        print("✅ 已执行 FLUSHDB")
        r.close()
        await r.wait_closed()
        
    except ImportError:
        print("ℹ️ aioredis 未安装，使用同步模式")
        clear_redis_cache_sync()


def main():
    print("=" * 50)
    print("🧹 Nautilus Trader Redis 缓存清除工具")
    print("=" * 50)
    
    # 检查是否有 TRADER_ID 或 NAUTILUS_DB 相关配置
    trader_id = os.getenv("TRADER_ID", "POLYMARKET-001")
    cache_type = os.getenv("CACHE_TYPE", "redis")
    
    print(f"📝 配置信息:")
    print(f"   - TRADER_ID: {trader_id}")
    print(f"   - CACHE_TYPE: {cache_type}")
    print()
    
    if cache_type.lower() not in ["redis", "in-memory"]:
        print(f"⚠️ 未知的缓存类型: {cache_type}")
    
    # 执行清除
    clear_redis_cache_sync()
    
    print()
    print("=" * 50)
    print("🎉 缓存清除完成！")
    print("=" * 50)
    print()
    print("提示: 现在可以重新启动 trading bot 了")
    print("命令: python live/run_polymarket_pde.py --mode sandbox")


if __name__ == "__main__":
    main()
