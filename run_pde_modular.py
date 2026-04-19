#!/usr/bin/env python3
"""
PDE Strategy Modular Runner

Example of how to run the modular PDE strategy.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modular strategy
from strategies.pde.main import PolymarketPDEStrategy, PolymarketPDEStrategyConfig


def main():
    """Run PDE strategy with configuration."""
    
    # Strategy configuration
    config = PolymarketPDEStrategyConfig(
        # Market settings
        market_base_slug="btc-updown-5m",
        market_interval_minutes=5,
        
        # Risk & execution
        max_position_usd=500.0,
        per_trade_usd=100.0,
        min_edge_threshold=0.02,
        max_slippage=0.005,
        spread_tolerance=0.05,
        
        # Phase parameters
        phase_a_duration_sec=240.0,
        tail_start_threshold=0.1,
        
        # BTC monitoring
        btc_jump_threshold_bps=50.0,
        btc_price_source="trade",  # "trade" or "mid"
        
        # Data refresh
        proactive_refresh_interval_min=10.0,
        flip_stats_refresh_minutes=30,
        flip_stats_lookback=200,
        
        # Display
        pnl_display_interval_sec=10.0,
        
        # Debug (set True for verbose logging)
        debug_raw_data=False,
        debug_ws=False,
    )
    
    # Create strategy instance
    strategy = PolymarketPDEStrategy(config)
    
    # The strategy is now ready to be used with NautilusTrader's backtester or live trader
    # For live trading, you would typically use:
    # 
    # from nautilus_trader.trading.trader import Trader
    # from nautilus_trader.system.kernel import NautilusKernel
    # 
    # kernel = NautilusKernel(config=nautilus_config)
    # trader = Trader(
    #     strategies=[strategy],
    #     data_engine=kernel.data_engine,
    #     risk_engine=kernel.risk_engine,
    #     exec_engine=kernel.exec_engine,
    # )
    # trader.start()
    
    print("✅ PDE Strategy (Modular) created successfully!")
    print(f"   Market: {config.market_base_slug}")
    print(f"   Max Position: ${config.max_position_usd}")
    print(f"   Per Trade: ${config.per_trade_usd}")
    print("\nTo run with NautilusTrader, integrate this strategy into your trading system.")
    
    return strategy


if __name__ == "__main__":
    strategy = main()
