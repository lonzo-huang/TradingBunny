# verify_polymarket.py
import sys
import importlib

print("=" * 60)
print("Nautilus Trader Polymarket 适配器验证")
print("=" * 60)

# 1. 检查 Python 版本
print(f"\n✅ Python 版本：{sys.version}")
if sys.version_info < (3, 12):
    print("⚠️  警告：建议使用 Python 3.12+")

# 2. 检查 nautilus_trader 版本
print("\n" + "-" * 60)
print("1. Nautilus Trader 版本检查")
print("-" * 60)
try:
    import nautilus_trader
    print(f"✅ 已安装：nautilus_trader v{nautilus_trader.__version__}")
except ImportError as e:
    print(f"❌ 未安装：{e}")
    sys.exit(1)

# 3. 检查 Polymarket 适配器模块
print("\n" + "-" * 60)
print("2. Polymarket 适配器模块检查")
print("-" * 60)

polymarket_modules = [
    "nautilus_trader.adapters.polymarket",
    "nautilus_trader.adapters.polymarket.config",
    "nautilus_trader.adapters.polymarket.data_client",
    "nautilus_trader.adapters.polymarket.execution_client",
]

for module in polymarket_modules:
    try:
        importlib.import_module(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module} - {e}")

# 4. 检查配置类
print("\n" + "-" * 60)
print("3. 配置类检查")
print("-" * 60)

config_classes = [
    ("PolymarketDataClientConfig", "nautilus_trader.adapters.polymarket.config"),
    ("PolymarketExecClientConfig", "nautilus_trader.adapters.polymarket.config"),
    ("PolymarketLiveConfig", "nautilus_trader.adapters.polymarket.config"),
]

for class_name, module_path in config_classes:
    try:
        module = importlib.import_module(module_path)
        getattr(module, class_name)
        print(f"✅ {class_name}")
    except (ImportError, AttributeError) as e:
        print(f"❌ {class_name} - {e}")

# 5. 检查数据加载器
print("\n" + "-" * 60)
print("4. PolymarketDataLoader 检查")
print("-" * 60)
try:
    from nautilus_trader.adapters.polymarket import PolymarketDataLoader
    print(f"✅ PolymarketDataLoader 可用")
    print(f"   位置：{PolymarketDataLoader.__module__}")
except ImportError as e:
    print(f"❌ PolymarketDataLoader - {e}")

# 6. 检查必要依赖
print("\n" + "-" * 60)
print("5. 依赖包检查")
print("-" * 60)

dependencies = [
    ("web3", "Web3 区块链交互"),
    ("aiohttp", "异步 HTTP"),
    ("pydantic", "配置验证"),
]

for package, description in dependencies:
    try:
        pkg = importlib.import_module(package)
        version = getattr(pkg, "__version__", "unknown")
        print(f"✅ {package} ({description}) - v{version}")
    except ImportError:
        print(f"❌ {package} ({description}) - 未安装")

# 7. 检查所有可用适配器
print("\n" + "-" * 60)
print("6. 所有可用适配器列表")
print("-" * 60)
try:
    import os
    adapters_path = os.path.dirname(
        importlib.import_module("nautilus_trader.adapters").__file__
    )
    adapters = [
        d for d in os.listdir(adapters_path)
        if os.path.isdir(os.path.join(adapters_path, d))
        and not d.startswith("_")
    ]
    print(f"可用适配器 ({len(adapters)} 个):")
    for adapter in sorted(adapters):
        marker = "🎯" if "polymarket" in adapter.lower() else "  "
        print(f"  {marker} {adapter}")
except Exception as e:
    print(f"❌ 无法列出适配器：{e}")

# 8. 检查 POLYMARKET_VENUE 常量
print("\n" + "-" * 60)
print("7. Polymarket 常量检查")
print("-" * 60)
try:
    from nautilus_trader.adapters.polymarket import POLYMARKET_VENUE
    print(f"✅ POLYMARKET_VENUE = {POLYMARKET_VENUE}")
except ImportError as e:
    print(f"❌ POLYMARKET_VENUE - {e}")

# 9. 总结
print("\n" + "=" * 60)
print("验证总结")
print("=" * 60)

# 计算通过率
checks = [
    "nautilus_trader" in sys.modules,
]

try:
    from nautilus_trader.adapters.polymarket import PolymarketDataLoader
    checks.append(True)
except:
    checks.append(False)

try:
    from nautilus_trader.adapters.polymarket.config import PolymarketDataClientConfig
    checks.append(True)
except:
    checks.append(False)

try:
    import web3
    checks.append(True)
except:
    checks.append(False)

passed = sum(checks)
total = len(checks)

if passed == total:
    print(f"\n✅ 所有检查通过 ({passed}/{total})")
    print("🎉 您的安装支持 Polymarket 集成！")
else:
    print(f"\n⚠️  部分检查未通过 ({passed}/{total})")
    print("📋 需要重新安装或安装额外依赖")

print("=" * 60)