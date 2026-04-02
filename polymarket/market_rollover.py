# polymarket/market_rollover.py
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict

class MarketRolloverManager:
    """市场轮转管理器"""
    
    def __init__(
        self,
        base_slug: str,
        interval_minutes: int = 5,
        api: PolymarketAPI = None,
    ):
        self.base_slug = base_slug
        self.interval_minutes = interval_minutes
        self.api = api or PolymarketAPI()
        self.current_market: Optional[Dict] = None
        self.next_rollover_time: int = 0
        self._connected = False
    
    async def connect(self) -> None:
        """连接 API"""
        await self.api.connect()
        self._connected = True
        await self._update_current_market()
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._connected:
            await self.api.disconnect()
            self._connected = False
    
    async def _update_current_market(self) -> None:
        """更新当前市场"""
        current_timestamp = int(time.time())
        self.next_rollover_time = self._get_next_interval_timestamp(current_timestamp)
        
        # 构建当前市场 slug
        current_market_slug = f"{self.base_slug}-{self.next_rollover_time}"
        
        # 查询市场是否存在
        market = await self.api.get_market_by_slug(current_market_slug)
        
        if market:
            self.current_market = market
            print(f"Current market: {market['slug']}")
            print(f"Ends at: {datetime.fromtimestamp(market.get('endTimestamp', 0))}")
        else:
            print(f"Market not found: {current_market_slug}")
            # 尝试查找最近的市场
            self.current_market = await self._find_nearest_market()
    
    def _get_next_interval_timestamp(self, current_timestamp: int) -> int:
        """获取下一个时间间隔的时间戳"""
        interval_seconds = self.interval_minutes * 60
        return (current_timestamp // interval_seconds + 1) * interval_seconds
    
    async def _find_nearest_market(self) -> Optional[Dict]:
        """查找最近的市场"""
        current_timestamp = int(time.time())
        
        # 搜索前后 5 个时间段的市场
        for offset in range(-5, 6):
            ts = current_timestamp + (offset * self.interval_minutes * 60)
            slug = f"{self.base_slug}-{ts}"
            market = await self.api.get_market_by_slug(slug)
            if market:
                return market
        
        return None
    
    def should_rollover(self) -> bool:
        """检查是否需要轮转"""
        return int(time.time()) >= self.next_rollover_time
    
    async def rollover(self) -> Optional[Dict]:
        """执行市场轮转"""
        if not self.should_rollover():
            return self.current_market
        
        await self._update_current_market()
        return self.current_market
    
    def get_time_until_rollover(self) -> int:
        """获取距离下次轮转的秒数"""
        return max(0, self.next_rollover_time - int(time.time()))
    
    def get_current_market_id(self) -> Optional[str]:
        """获取当前市场 ID"""
        if self.current_market:
            return self.current_market.get("slug")
        return None
    
    def get_current_instrument_id(self) -> Optional[str]:
        """获取当前工具 ID"""
        market_id = self.get_current_market_id()
        if market_id:
            return f"{market_id}.POLYMARKET"
        return None

# 使用示例
async def market_rollover_demo():
    manager = MarketRolloverManager(
        base_slug="btc-updown-5m",
        interval_minutes=5,
    )
    
    await manager.connect()
    
    print(f"Current market: {manager.get_current_market_id()}")
    print(f"Time until rollover: {manager.get_time_until_rollover()} seconds")
    
    # 等待轮转
    while True:
        await asyncio.sleep(60)
        
        if manager.should_rollover():
            print("Rollover triggered!")
            old_market = manager.get_current_market_id()
            await manager.rollover()
            new_market = manager.get_current_market_id()
            print(f"Market changed: {old_market} -> {new_market}")

# asyncio.run(market_rollover_demo())