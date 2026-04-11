#!/usr/bin/env python3
"""
修复重复 trade_id 问题的专用脚本
这个脚本会:
1. 清除 Redis 中的 positions/orders/trades 缓存
2. 查找并删除本地 SQLite 缓存文件（如果使用）
"""
import os
import sys
import glob
import shutil
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
project_root = Path(__file__).parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)


def clear_redis_trades():
    """清除 Redis 中的 trade 相关缓存"""
    try:
        import redis
        
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        print(f"🔌 连接 Redis {redis_host}:{redis_port}/{redis_db}...")
        r = redis.Redis(
            host=redis_host, port=redis_port, db=redis_db,
            password=redis_password if redis_password else None,
            decode_responses=True
        )
        r.ping()
        print("✅ Redis 连接成功")
        
        trader_id = os.getenv("TRADER_ID", "POLYMARKET-001")
        
        # 要删除的 key 模式
        patterns = [
            f"{trader_id}:positions*",
            f"{trader_id}:orders*",
            f"{trader_id}:trades*",
            f"{trader_id}:fills*",
            "*POLYMARKET-168*",  # 特定问题 trade_id
        ]
        
        total_deleted = 0
        for pattern in patterns:
            keys = r.keys(pattern)
            if keys:
                deleted = r.delete(*keys)
                total_deleted += deleted
                print(f"🗑️  删除 {len(keys)} 个 keys (模式: {pattern})")
        
        print(f"✅ 共删除 {total_deleted} 个 Redis keys")
        
        # 可选: 完全清空当前数据库
        flush = input("\n⚠️  是否执行 FLUSHDB 完全清除当前 Redis 数据库? (yes/no): ")
        if flush.lower() == "yes":
            r.flushdb()
            print("✅ 已执行 FLUSHDB")
            
    except ImportError:
        print("❌ 请先安装 redis: pip install redis")
    except Exception as e:
        print(f"❌ Redis 错误: {e}")


def find_and_clear_sqlite_cache():
    """查找并清除本地 SQLite 缓存文件"""
    print("\n🔍 查找本地 SQLite 缓存文件...")
    
    # 常见缓存目录
    cache_dirs = [
        project_root / "cache",
        project_root / "data" / "cache",
        project_root / ".cache",
        Path.home() / ".nautilus" / "cache",
        Path.home() / ".cache" / "nautilus",
    ]
    
    found_files = []
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            # 查找 SQLite 文件
            patterns = ["*.db", "*.sqlite", "*.sqlite3", "*cache*"]
            for pattern in patterns:
                files = list(cache_dir.glob(pattern))
                found_files.extend(files)
    
    # 也查找项目根目录
    for pattern in ["*.db", "*.sqlite", "*trades*", "*positions*"]:
        files = list(project_root.glob(pattern))
        found_files.extend(files)
    
    # 去重
    found_files = list(set(found_files))
    
    if not found_files:
        print("ℹ️ 没有找到本地 SQLite 缓存文件")
        return
    
    print(f"📁 找到 {len(found_files)} 个文件:")
    for f in found_files:
        size = f.stat().st_size / 1024  # KB
        print(f"   - {f} ({size:.1f} KB)")
    
    response = input(f"\n⚠️  确定要删除这 {len(found_files)} 个文件吗? (yes/no): ")
    if response.lower() != "yes":
        print("❌ 已取消")
        return
    
    for f in found_files:
        try:
            if f.is_file():
                f.unlink()
                print(f"🗑️  删除: {f.name}")
            elif f.is_dir():
                shutil.rmtree(f)
                print(f"🗑️  删除目录: {f.name}")
        except Exception as e:
            print(f"❌ 删除失败 {f}: {e}")
    
    print(f"✅ 本地缓存清理完成")


def main():
    print("=" * 60)
    print("🛠️  修复重复 Trade ID 问题")
    print("=" * 60)
    print()
    print("问题原因: Nautilus 在 Redis/SQLite 中缓存了重复的数据")
    print("解决方案: 清除所有相关缓存")
    print()
    
    # 1. 清除 Redis
    print("【步骤 1/2】清除 Redis 缓存")
    print("-" * 40)
    clear_redis_trades()
    
    # 2. 清除本地文件
    print()
    print("【步骤 2/2】清除本地 SQLite 缓存")
    print("-" * 40)
    find_and_clear_sqlite_cache()
    
    print()
    print("=" * 60)
    print("✅ 缓存清理完成!")
    print("=" * 60)
    print()
    print("现在可以重新启动 bot:")
    print("  python live/run_polymarket_pde.py --mode sandbox")
    print()
    print("如果问题仍然存在，建议:")
    print("1. 检查 .env 中的 REDIS_DB 配置，尝试切换到不同的 DB (0-15)")
    print("2. 重启 Redis 服务器")
    print("3. 使用 redis-cli 手动检查: KEYS *POLYMARKET*")


if __name__ == "__main__":
    main()
