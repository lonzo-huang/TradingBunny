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
    print(f"[OK] 成功加载环境变量文件：{env_file}")
else:
    print(f"[WARN] 未找到 .env 文件：{env_file}")

pk = os.getenv("POLYMARKET_PK")
funder = os.getenv("POLYMARKET_FUNDER")
if pk and funder:
    print(f"[OK] 检测到 POLYMARKET_PK (结尾...{pk[-6:]})")
    print(f"[OK] 检测到 POLYMARKET_FUNDER (结尾...{funder[-6:]})")
else:
    print("[WARN] 密钥仍未读取到，请检查 .env 内容格式。")

# ==========================================================
# Imports
# ==========================================================
try:
    from nautilus_trader.live.node import TradingNode
    from config.polymarket_pde_config import configure_pde_node

    try:
        from nautilus_trader.adapters.polymarket import register_polymarket_adapters
        from nautilus_trader.adapters.sandbox import register_sandbox_adapters
        print("[OK] 成功导入适配器注册函数！")
    except ImportError:
        print("[WARN] 未找到自动注册函数，将尝试手动注册...")
        register_polymarket_adapters = None
        register_sandbox_adapters = None

    print("[OK] 成功导入 PDE 配置模块！")
except ModuleNotFoundError as e:
    print(f"[ERROR] 导入失败：{e}")
    print("[HINT] 解决方法：请确保 config/ 和 strategies/ 文件夹下有 __init__.py 文件！")
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
            print(f"\n[WARN] 收到停止信号 {signum}. 正在关闭...")
            self._shutdown = True
            if hasattr(self, '_loop'):
                self._loop.call_soon_threadsafe(self._shutdown_event.set)

    async def run(self):
        self.node = TradingNode(config=self.config)
        self._loop = asyncio.get_running_loop()
        self.setup_signal_handlers()

        try:
            print("[START] 正在注册适配器工厂 (PDE Strategy)...")

            if register_polymarket_adapters:
                register_polymarket_adapters()
                print("[OK] Polymarket 适配器已注册")
            else:
                print("[WARN] 无法自动注册 Polymarket")

            if register_sandbox_adapters:
                register_sandbox_adapters()
                print("[OK] Sandbox 适配器已注册")

            print("[START] 正在构建交易节点客户端 (PDE)...")

            self.node.add_data_client_factory("POLYMARKET", PolymarketLiveDataClientFactory)
            self.node.add_data_client_factory("BINANCE", BinanceLiveDataClientFactory)
            print("[OK] Binance 数据客户端工厂已添加")

            if "SANDBOX" in self.config.exec_clients:
                self.node.add_exec_client_factory("SANDBOX", SandboxLiveExecClientFactory)
                print("[OK] Sandbox 执行客户端工厂已添加")

            if "POLYMARKET" in self.config.exec_clients:
                self.node.add_exec_client_factory("POLYMARKET", PolymarketLiveExecClientFactory)
                print("[OK] Polymarket 执行客户端工厂已添加")

            self.node.build()

            print("[OK] PDE 客户端构建成功！正在启动引擎...")

            node_task = asyncio.create_task(self.node.run_async())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())

            print("[OK] PDE 节点运行中。按 Ctrl+C 停止...")

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
            print(f"[ERROR] 严重错误：{e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            await self.stop()

    async def stop(self):
        if self.node:
            print("[STOP] 正在停止 PDE 交易节点...")
            try:
                self.node.stop()
                self.node.dispose()
                print("[OK] PDE 交易节点已停止。")
            except Exception as e:
                print(f"[WARN] 停止节点时出错：{e}")

        if self._shutdown:
            print("[BYE] 程序即将退出...")


def _flush_sandbox_redis(trader_id: str = "POLYMARKET-SBX") -> None:
    """
    清除 sandbox trader 在 Redis 中的缓存状态。
    每次 sandbox 启动前调用，确保从 starting_balances 重新初始化，
    避免残留的虚拟账户/持仓/订单状态干扰新一轮运行。
    Live 数据（POLYMARKET-001）不受影响。
    """
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    try:
        import redis as redis_lib
        r = redis_lib.Redis(host=redis_host, port=redis_port, socket_connect_timeout=2)
        pattern = f"trader-{trader_id}:*"
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
            print(f"[OK] 已清除 sandbox Redis 缓存: {len(keys)} 条 (trader_id={trader_id})")
        else:
            print(f"[OK] sandbox Redis 无历史缓存 (trader_id={trader_id})")
    except Exception as e:
        print(f"[WARN] 清除 sandbox Redis 缓存失败（可忽略）: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Polymarket PDE Strategy Bot")
    parser.add_argument(
        "--mode",
        choices=["sandbox", "live", "both"],
        default="sandbox",
        help="Execution mode: sandbox (paper trading), live (real money), both"
    )
    args = parser.parse_args()

    print(f"[START] PDE 策略启动模式: {args.mode}")

    # sandbox 每次启动前清除 Redis 旧状态，保证从 starting_balances 重新初始化
    if args.mode == "sandbox":
        sandbox_trader_id = os.getenv("NAUTILUS_TRADER_ID", "POLYMARKET-SBX")
        _flush_sandbox_redis(sandbox_trader_id)

    if args.mode == "both":
        # 启动两个独立子进程：一个 sandbox，一个 live
        # 各自拥有独立 TradingNode，避免 venue ID 冲突
        # sandbox 使用不同的 trader_id (POLYMARKET-SBX)，防止 Redis 命名空间与 live 冲突
        import subprocess
        procs = []

        # 给 sandbox 子进程注入不同的 trader_id 和 WebSocket 端口，避免与 live 进程冲突
        sandbox_env = os.environ.copy()
        sandbox_env["NAUTILUS_TRADER_ID"] = "POLYMARKET-SBX"
        sandbox_env["LIVE_STREAM_PORT"] = "8768"   # live: WS=8765 HTTP=8766, sandbox: WS=8768 HTTP=8769

        # 启动前预清除 sandbox Redis，子进程里的 _flush_sandbox_redis 也会执行一次（幂等）
        _flush_sandbox_redis("POLYMARKET-SBX")

        try:
            sandbox_proc = subprocess.Popen(
                [sys.executable, __file__, "--mode", "sandbox"],
                env=sandbox_env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            procs.append(("sandbox", sandbox_proc))
            print(f"[OK] Sandbox 子进程已启动 (PID={sandbox_proc.pid}, WS=:8768/HTTP=:8769, trader=POLYMARKET-SBX)")

            live_proc = subprocess.Popen(
                [sys.executable, __file__, "--mode", "live"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            procs.append(("live", live_proc))
            print(f"[OK] Live 子进程已启动 (PID={live_proc.pid}, WS=:8765/HTTP=:8766, trader=POLYMARKET-001)")

            print("[OK] 两个实例均已启动，按 Ctrl+C 同时停止所有进程...")

            # 等待任意一个进程退出
            loop = asyncio.get_running_loop()
            while True:
                await asyncio.sleep(1)
                for name, proc in procs:
                    if proc.poll() is not None:
                        print(f"[WARN] {name} 进程已退出 (code={proc.returncode})，停止所有进程...")
                        return

        except KeyboardInterrupt:
            print("\n[WARN] 收到停止信号，正在终止所有子进程...")
        finally:
            for name, proc in procs:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        print(f"[OK] {name} 进程已停止")
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        print(f"[WARN] {name} 进程强制终止")
        return

    config = configure_pde_node(execution_mode=args.mode)
    bot = PDETradingBot(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
