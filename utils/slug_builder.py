# utils/slug_builder.py
from datetime import datetime, timezone, timedelta

def build_btc_updown_slugs() -> list[str]:
    """返回当前及未来多个 5 分钟窗口的 slug，供 PolymarketInstrumentProvider 加载
    
    加载当前及接下来 23 个窗口（共 2 小时），确保市场滚动时 instrument 始终可用。
    Provider 每次 refresh 会重新调用此函数，生成基于当前时间的新窗口。
    """
    now = datetime.now(timezone.utc)
    interval = 5  # 5 分钟间隔
    
    # 计算当前对齐的窗口
    aligned_minute = (now.minute // interval) * interval
    current = now.replace(minute=aligned_minute, second=0, microsecond=0)
    
    # 生成当前 + 未来 23 个窗口的 slugs（共 2 小时缓冲）
    # Provider 每次 refresh 会重新调用此函数，生成基于当前时间的新窗口。
    # 策略会在半程（1h）主动触发 refresh，确保长期运行缓存不断档。
    slugs = []
    base = "btc-updown-5m"
    
    for i in range(24):
        window_time = current + timedelta(minutes=interval * i)
        slug = f"{base}-{int(window_time.timestamp())}"
        slugs.append(slug)
    
    return slugs