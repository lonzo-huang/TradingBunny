# live/run_polymarket_pde.py
"""
Launch script for Polymarket PDE Strategy (Dual-Phase Engine)
Usage: python live/run_polymarket_pde.py --mode sandbox
"""
import asyncio
import signal
import sys
import os
import argparse
from pathlib import Path
from nautilus_trader.adapters.polymarket.factories import PolymarketLiveDataClientFactory, PolymarketLiveExecClientFactory
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.adapters.binance.factories import BinanceLiveDataClientFactory

# ==========================================================
# 🔧 Project root on sys.path
# ==========================================================
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 🔧 Load .env
from dotenv import load_dotenv
env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"✅ 成功加载环境变量文件：{env_file}")
else:
    print(f"❌ 警告：未找到 .env 文件：{env_file}")

pk = os.getenv("POLYMARKET_PK")
funder = os.getenv("POLYMARKET_FUNDER")
if pk and funder:
    print(f"✅ 检测到 POLYMARKET_PK (结尾...{pk[-6:]})")
    print(f"✅ 检测到 POLYMARKET_FUNDER (结尾...{funder[-6:]})")
else:
    print("⚠️ 警告：密钥仍未读取到，请检查 .env 内容格式。")

# ==========================================================
# Imports
# ==========================================================
try:
    from nautilus_trader.live.node import TradingNode
    from config.polymarket_pde_config import configure_pde_node

    try:
        from nautilus_trader.adapters.polymarket import register_polymarket_adapters
        from nautilus_trader.adapters.sandbox import register_sandbox_adapters
        print("✅ 成功导入适配器注册函数！")
    except ImportError:
        print("⚠️ 未找到自动注册函数，将尝试手动注册...")
        register_polymarket_adapters = None
        register_sandbox_adapters = None

    print("✅ 成功导入 PDE 配置模块！")
except ModuleNotFoundError as e:
    print(f"❌ 导入失败：{e}")
    print("💡 解决方法：请确保 config/ 和 strategies/ 文件夹下有 __init__.py 文件！")
    sys.exit(1)


class PDETradingBot:
    def __init__(self, config):
        self.config = config
        self.node = None
        self._shutdown = False
        self._shutdown_event = asyncio.Event()

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        if not self._shutdown:
            print(f"\n⚠️  收到停止信号 {signum}. 正在关闭...")
            self._shutdown = True
            if hasattr(self, '_loop'):
                self._loop.call_soon_threadsafe(self._shutdown_event.set)

    async def run(self):
        self.node = TradingNode(config=self.config)
        self._loop = asyncio.get_running_loop()
        self.setup_signal_handlers()

        try:
            print("🚀 正在注册适配器工厂 (PDE Strategy)...")

            if register_polymarket_adapters:
                register_polymarket_adapters()
                print("✅ Polymarket 适配器已注册")
            else:
                print("⚠️ 无法自动注册 Polymarket")

            if register_sandbox_adapters:
                register_sandbox_adapters()
                print("✅ Sandbox 适配器已注册")

            print("🚀 正在构建交易节点客户端 (PDE)...")

            self.node.add_data_client_factory("POLYMARKET", PolymarketLiveDataClientFactory)
            self.node.add_data_client_factory("BINANCE", BinanceLiveDataClientFactory)
            print("✅ Binance 数据客户端工厂已添加")

            if "SANDBOX" in self.config.exec_clients:
                self.node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
                print("✅ Sandbox 执行客户端工厂已添加")

            if "POLYMARKET" in self.config.exec_clients:
                self.node.add_exec_client_factory("POLYMARKET", PolymarketLiveExecClientFactory)
                print("✅ Polymarket 执行客户端工厂已添加")

            self.node.build()

            print("✅ PDE 客户端构建成功！正在启动引擎...")

            node_task = asyncio.create_task(self.node.run_async())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())

            print("✅ PDE 节点运行中。按 Ctrl+C 停止...")

            done, pending = await asyncio.wait(
                [node_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Re-raise any exception from completed tasks
            for task in done:
                if task.exception():
                    raise task.exception()

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            print(f"❌ 严重错误：{e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            await self.stop()

    async def stop(self):
        if self.node:
            print("🛑 正在停止 PDE 交易节点...")
            try:
                self.node.stop()
                self.node.dispose()
                print("✅ PDE 交易节点已停止。")
            except Exception as e:
                print(f"⚠️  停止节点时出错：{e}")

        if self._shutdown:
            print("👋 程序即将退出...")


async def main():
    parser = argparse.ArgumentParser(description="Polymarket PDE Strategy Bot")
    parser.add_argument(
        "--mode",
        choices=["sandbox", "live", "both"],
        default="sandbox",
        help="Execution mode: sandbox (paper trading), live (real money), both"
    )
    args = parser.parse_args()

    print(f"🎯 PDE 策略启动模式: {args.mode}")
    config = configure_pde_node(execution_mode=args.mode)
    bot = PDETradingBot(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
