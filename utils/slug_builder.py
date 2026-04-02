# utils/slug_builder.py
from datetime import datetime, timezone, timedelta

def build_btc_updown_slugs() -> list[str]:
    """返回当前及未来多个 5 分钟窗口的 slug，供 PolymarketInstrumentProvider 加载
    
    加载当前及接下来 6 个窗口（共 30 分钟），确保市场滚动时 instrument 始终可用。
    """
    now = datetime.now(timezone.utc)
    interval = 5  # 5 分钟间隔
    
    # 计算当前对齐的窗口
    aligned_minute = (now.minute // interval) * interval
    current = now.replace(minute=aligned_minute, second=0, microsecond=0)
    
    # 生成当前 + 未来 6 个窗口的 slugs（共 30 分钟缓冲）
    slugs = []
    base = "btc-updown-5m"
    
    for i in range(7):  # 0 到 6，共 7 个窗口 = 35 分钟
        window_time = current + timedelta(minutes=interval * i)
        slug = f"{base}-{int(window_time.timestamp())}"
        slugs.append(slug)
    
    return slugs