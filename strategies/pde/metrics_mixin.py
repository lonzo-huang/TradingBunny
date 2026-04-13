"""Metrics and monitoring mixin: Prometheus gauges, health checks."""

from __future__ import annotations

from typing import Any


class PDEMetricsMixin:
    """Handles Prometheus metrics and health monitoring."""
    
    # Required from base
    config: Any
    log: Any
    rounds_counter: Any | None
    btc_price_gauge: Any | None
    btc_momentum_gauge: Any | None
    btc_delta_p_gauge: Any | None
    latency_gap_gauge: Any | None
    position_gauge: Any | None
    phase_a_trades_gauge: Any | None
    phase_b_trades_gauge: Any | None
    pnl_gauge: Any | None
    total_pnl_gauge: Any | None
    positions: dict
    A_trades: int
    B_trades: int
    total_pnl: float
    
    def _setup_prometheus_metrics(self) -> None:
        """Initialize Prometheus monitoring metrics."""
        try:
            from prometheus_client import Gauge, Counter
            
            self.rounds_counter = Counter(
                'pde_rounds_total', 
                'Total number of trading rounds completed'
            )
            
            self.btc_price_gauge = Gauge(
                'pde_btc_price', 
                'Current BTC price'
            )
            
            self.btc_momentum_gauge = Gauge(
                'pde_btc_momentum_bps', 
                'BTC momentum in basis points'
            )
            
            self.btc_delta_p_gauge = Gauge(
                'pde_btc_delta_p', 
                'BTC delta from round start'
            )
            
            self.latency_gap_gauge = Gauge(
                'pde_latency_gap_ms', 
                'Latency gap between BTC and Polymarket in ms'
            )
            
            self.position_gauge = Gauge(
                'pde_position_exposure_usd', 
                'Current position exposure in USD',
                ['token']
            )
            
            self.phase_a_trades_gauge = Gauge(
                'pde_phase_a_trades', 
                'Number of Phase A trades in current round'
            )
            
            self.phase_b_trades_gauge = Gauge(
                'pde_phase_b_trades', 
                'Number of Phase B trades in current round'
            )
            
            self.pnl_gauge = Gauge(
                'pde_round_pnl', 
                'Current round PnL'
            )
            
            self.total_pnl_gauge = Gauge(
                'pde_total_pnl', 
                'Cumulative total PnL'
            )
            
            self.log.info("📊 Prometheus metrics initialized")
            
        except ImportError:
            self.log.warning("⚠️ prometheus_client not available, metrics disabled")
            # Create dummy objects
            class DummyMetric:
                def set(self, *args, **kwargs): pass
                def inc(self, *args, **kwargs): pass
                def _value(self): return 0
            
            self.rounds_counter = type('obj', (object,), {'inc': lambda self: None})()
            self.btc_price_gauge = DummyMetric()
            self.btc_momentum_gauge = DummyMetric()
            self.btc_delta_p_gauge = DummyMetric()
            self.latency_gap_gauge = DummyMetric()
            self.position_gauge = type('obj', (object,), {'labels': lambda *args: DummyMetric()})()
            self.phase_a_trades_gauge = DummyMetric()
            self.phase_b_trades_gauge = DummyMetric()
            self.pnl_gauge = DummyMetric()
            self.total_pnl_gauge = DummyMetric()
    
    def _update_metrics(self) -> None:
        """Update all Prometheus metrics."""
        # Update position gauges
        for token_key in ('up', 'down'):
            pos = self.positions[token_key]
            if pos['open']:
                exposure = pos['size'] * pos['entry_price']
            else:
                exposure = 0.0
            try:
                self.position_gauge.labels(token=token_key).set(exposure)
            except Exception:
                pass
        
        # Update trade counters
        try:
            self.phase_a_trades_gauge.set(self.A_trades)
            self.phase_b_trades_gauge.set(self.B_trades)
        except Exception:
            pass
        
        # Update PnL
        try:
            self.total_pnl_gauge.set(self.total_pnl)
        except Exception:
            pass
    
    def _get_health_score(self) -> tuple[int, dict]:
        """Calculate health score and status."""
        score = 100
        items = {}
        
        # Check positions
        open_positions = sum(1 for p in self.positions.values() if p['open'])
        items['positions'] = 'ok' if open_positions <= 2 else 'warn'
        
        # Check BTC price
        if hasattr(self, 'btc_price') and self.btc_price is not None:
            items['btc_feed'] = 'ok'
        else:
            items['btc_feed'] = 'fail'
            score -= 20
        
        # Check market subscription
        if hasattr(self, 'instrument') and self.instrument is not None:
            items['market_sub'] = 'ok'
        else:
            items['market_sub'] = 'fail'
            score -= 30
        
        # Check WebSocket
        if hasattr(self, 'live_server') and self.live_server is not None:
            items['websocket'] = 'ok'
        else:
            items['websocket'] = 'warn'
            score -= 10
        
        return max(0, score), items
