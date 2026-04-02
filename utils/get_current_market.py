# utils/get_current_market.py
import asyncio
import time
from datetime import datetime, timezone
from nautilus_trader.adapters.polymarket import PolymarketDataLoader

class PolymarketMarketFinder:
    """Polymarket 市场查找器"""
    
    @staticmethod
    def get_current_timestamp(interval_minutes: int = 5) -> int:
        """获取当前时间段的时间戳"""
        now = datetime.now(timezone.utc)
        minutes = (now.minute // interval_minutes) * interval_minutes
        market_time = now.replace(minute=minutes, second=0, microsecond=0)
        return int(market_time.timestamp())
    
    @staticmethod
    async def get_current_btc_5m_market():
        """获取当前 BTC 5 分钟市场"""
        timestamp = PolymarketMarketFinder.get_current_timestamp(5)
        slug = f"btc-updown-5m-{timestamp}"
        
        try:
            loader = await PolymarketDataLoader.from_market_slug(slug)
            print(f"✅ Found market: {slug}")
            print(f"   Instrument: {loader.instrument}")
            print(f"   Token ID: {loader.token_id}")
            print(f"   Condition ID: {loader.condition_id}")
            return loader
        except Exception as e:
            print(f"⚠️  Market not found: {slug}")
            print(f"   Error: {e}")
            return await PolymarketMarketFinder._find_nearest_market()
    
    @staticmethod
    async def _find_nearest_market():
        """查找最近的市场"""
        current_ts = int(time.time())
        interval = 5 * 60  # 5 分钟
        
        for offset in range(-5, 6):
            ts = current_ts + (offset * interval)
            slug = f"btc-updown-5m-{ts}"
            try:
                loader = await PolymarketDataLoader.from_market_slug(slug)
                print(f"✅ Found nearest market: {slug}")
                return loader
            except:
                continue
        
        print("❌ No market found in range")
        return None

if __name__ == "__main__":
    finder = PolymarketMarketFinder()
    asyncio.run(finder.get_current_btc_5m_market())