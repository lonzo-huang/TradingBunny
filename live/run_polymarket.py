# live/run_polymarket.py
import asyncio
import signal
import sys
import os
import argparse
from pathlib import Path
from nautilus_trader.adapters.polymarket.factories import PolymarketLiveDataClientFactory, PolymarketLiveExecClientFactory
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory

# ==========================================================
# 🔧 关键修复 1: 强制将项目根目录加入 Python 搜索路径
# ==========================================================
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 🔧 关键修复 2: 加载 .env 文件
from dotenv import load_dotenv
env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"✅ 成功加载环境变量文件：{env_file}")
else:
    print(f"❌ 警告：未找到 .env 文件：{env_file}")

# 验证密钥是否读取成功
pk = os.getenv("POLYMARKET_PK")
funder = os.getenv("POLYMARKET_FUNDER")
if pk and funder:
    print(f"✅ 检测到 POLYMARKET_PK (结尾...{pk[-6:]})")
    print(f"✅ 检测到 POLYMARKET_FUNDER (结尾...{funder[-6:]})")
else:
    print("⚠️ 警告：密钥仍未读取到，请检查 .env 内容格式。")

# ==========================================================
# 正常导入后续模块
# ==========================================================
try:
    from nautilus_trader.live.node import TradingNode
    from config.polymarket_config import configure_polymarket_node
    
    # ✅ 关键修复 3: 导入适配器工厂注册函数
    # 注意：不同版本路径可能不同，以下是常见路径
    try:
        from nautilus_trader.adapters.polymarket import register_polymarket_adapters
        from nautilus_trader.adapters.sandbox import register_sandbox_adapters
        print("✅ 成功导入适配器注册函数！")
    except ImportError:
        # 如果找不到注册函数，尝试直接导入客户端类并在下面手动注册
        print("⚠️ 未找到自动注册函数，将尝试手动注册...")
        register_polymarket_adapters = None
        register_sandbox_adapters = None
        
    print("✅ 成功导入配置模块！")
except ModuleNotFoundError as e:
    print(f"❌ 导入失败：{e}")
    print("💡 解决方法：请确保 config/ 和 strategies/ 文件夹下有 __init__.py 文件！")
    sys.exit(1)

class PolymarketTradingBot:
    def __init__(self, config):
        self.config = config
        self.node = None
        self._shutdown = False
        self._shutdown_event = asyncio.Event()  # 添加异步事件
    
    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        if not self._shutdown:  # 只处理第一次信号
            print(f"\n⚠️  收到停止信号 {signum}. 正在关闭...")
            self._shutdown = True
            # 设置事件来唤醒等待的协程
            if hasattr(self, '_loop'):
                self._loop.call_soon_threadsafe(self._shutdown_event.set)
    
    async def run(self):
        # 1. 创建节点
        self.node = TradingNode(config=self.config)
        self.setup_signal_handlers()
        
        # 保存事件循环引用
        self._loop = asyncio.get_running_loop()
        
        try:
            print("🚀 正在注册适配器工厂...")
            
            # ✅ 关键修复 4: 手动注册适配器工厂
            if register_polymarket_adapters:
                register_polymarket_adapters()
                print("✅ Polymarket 适配器已注册")
            else:
                # 如果没有注册函数，尝试手动添加 (高级用法，视版本而定)
                # 这里可能需要根据具体版本调整，如果上面导入失败，这里可能也需要特殊处理
                # 对于大多数情况，只要配置正确，build() 会自动处理，但如果报错 "No factory registered"
                # 说明必须显式调用注册函数。
                print("⚠️ 无法自动注册 Polymarket，请检查 Nautilus Trader 版本文档。")
                
            if register_sandbox_adapters:
                register_sandbox_adapters()
                print("✅ Sandbox 适配器已注册")
            
            print("🚀 正在构建交易节点客户端 (Data & Exec Clients)...")
            
            # 2. 构建客户端
            self.node.add_data_client_factory("POLYMARKET", PolymarketLiveDataClientFactory)
            
            # 根据配置的执行客户端添加对应的工厂
            if "SANDBOX" in self.config.exec_clients:
                self.node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
                print("✅ Sandbox 执行客户端工厂已添加")
            
            if "POLYMARKET" in self.config.exec_clients:
                self.node.add_exec_client_factory("POLYMARKET", PolymarketLiveExecClientFactory)
                print("✅ Polymarket 执行客户端工厂已添加")
            
            self.node.build() 
            
            print("✅ 客户端构建成功！正在启动引擎...")
            
            # 启动节点但不无限等待
            node_task = asyncio.create_task(self.node.run_async())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            print("✅ 节点运行中。按 Ctrl+C 停止...")
            
            # 等待停止信号或节点任务完成
            done, pending = await asyncio.wait(
                [node_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消未完成的任务
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
            print("🛑 正在停止交易节点...")
            try:
                self.node.stop()
                self.node.dispose()
                print("✅ 交易节点已停止。")
            except Exception as e:
                print(f"⚠️  停止节点时出错：{e}")
        
        # 确保程序退出
        if self._shutdown:
            print("👋 程序即将退出...")
            # 强制退出
            import os
            os._exit(0)

async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Polymarket Trading Bot")
    parser.add_argument(
        "--mode", 
        choices=["sandbox", "live", "both"], 
        default="sandbox",
        help="Execution mode: sandbox (paper trading), live (real money), both (both clients)"
    )
    args = parser.parse_args()
    
    print(f"🎯 启动模式: {args.mode}")
    config = configure_polymarket_node(execution_mode=args.mode)
    bot = PolymarketTradingBot(config)
    await bot.run()

if __name__ == "__main__":
    # 确保安装了 python-dotenv: pip install python-dotenv
    asyncio.run(main())