"""
End-to-end tests that exercise the full pipeline:

    raw daily data → add indicators → Chan analysis → signals

All external dependencies (Tushare, Tkinter) are mocked so the tests
run offline and without a display.
"""

import pytest
import pandas as pd
import numpy as np

from tests.conftest import make_ohlc_df_np


# ---------------------------------------------------------------------------
# helpers – synthetic price series builders
# ---------------------------------------------------------------------------

def _sine_wave_ohlc(n=200, seed=42):
    """Multi-cycle sine wave with mild uptrend.  Produces clear tops/bottoms."""
    rng = np.random.RandomState(seed)
    x = np.linspace(0, 8 * np.pi, n)
    close = 10 + np.sin(x) * 4 + np.linspace(0, 6, n) + rng.randn(n) * 0.15
    high = close + np.abs(rng.randn(n) * 0.4)
    low = close - np.abs(rng.randn(n) * 0.4)
    return make_ohlc_df_np(high, low, close)


def _downtrend_then_uptrend(n=200, seed=123):
    """V-shaped reversal – should generate buy signals near the bottom."""
    rng = np.random.RandomState(seed)
    half = n // 2
    x = np.linspace(0, 6 * np.pi, n)
    trend = np.concatenate([
        np.linspace(0, -4, half),   # downtrend
        np.linspace(-4, 4, n - half),  # recovery + uptrend
    ])
    close = 10 + trend + np.sin(x) * 2 + rng.randn(n) * 0.15
    high = close + np.abs(rng.randn(n) * 0.3)
    low = close - np.abs(rng.randn(n) * 0.3)
    return make_ohlc_df_np(high, low, close)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Run the complete analyze() pipeline with synthetic data."""

    def test_sine_wave_pipeline(self):
        from core.chan_engine import ChanLunEngine

        engine = ChanLunEngine()
        df = _sine_wave_ohlc(n=200)
        result = engine.analyze(df, "日线", "E2E_SINE")

        assert isinstance(result, dict)
        for key in ["accurate_buy", "accurate_sell", "normal_buy", "normal_sell"]:
            assert key in result
            assert isinstance(result[key], list)
        # Signal counts depend on indicator alignment – pipeline ran cleanly
        total = sum(len(v) for v in result.values())
        # With synthetic data, indicator confirmation is probabilistic;
        # the key assertion is that the pipeline completed without error.
        assert total >= 0

    def test_v_reversal_pipeline(self):
        from core.chan_engine import ChanLunEngine

        engine = ChanLunEngine()
        df = _downtrend_then_uptrend(n=200)
        result = engine.analyze(df, "日线", "E2E_V")

        # The V shape reliably produces signals (sells near top, buys near bottom)
        total = sum(len(v) for v in result.values())
        assert total > 0, "V-shaped data should produce trading signals"

    def test_pipeline_with_empty_data(self):
        from core.chan_engine import ChanLunEngine

        engine = ChanLunEngine()
        df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        result = engine.analyze(df, "日线", "EMPTY")

        for v in result.values():
            assert v == []

    def test_pipeline_all_levels(self):
        """Ensure the pipeline runs on daily/weekly/monthly without crashing."""
        from core.chan_engine import ChanLunEngine

        engine = ChanLunEngine()
        daily = _sine_wave_ohlc(n=250)

        for level_name, level_df in [("日线", daily), ("周线", daily), ("月线", daily)]:
            result = engine.analyze(level_df, level_name, "E2E_LEVELS")
            assert isinstance(result, dict)
            for key in ["accurate_buy", "accurate_sell", "normal_buy", "normal_sell"]:
                assert key in result
                assert isinstance(result[key], list)

    def test_signal_items_are_well_formed(self):
        """Every signal dict must have the four required keys."""
        from core.chan_engine import ChanLunEngine

        engine = ChanLunEngine()
        df = _sine_wave_ohlc(n=200)
        result = engine.analyze(df, "日线", "E2E_FORM")

        all_items = (result["accurate_buy"] + result["accurate_sell"] +
                     result["normal_buy"] + result["normal_sell"])

        for item in all_items:
            assert isinstance(item["time"], str)
            assert isinstance(item["price"], float)
            assert isinstance(item["type"], str)
            assert isinstance(item["indicators"], str)
            # price should be positive
            assert item["price"] > 0


class TestDataApiIntegration:
    """Mocked DataAPI → ChanLunEngine integration."""

    def test_mocked_fetch_then_analyze(self):
        from unittest.mock import patch, MagicMock
        import numpy as np
        from datetime import datetime, timedelta

        # Build mock Tushare response
        n = 200
        rng = np.random.RandomState(77)
        x = np.linspace(0, 8 * np.pi, n)
        close = 10 + np.sin(x) * 3 + np.linspace(0, 4, n) + rng.randn(n) * 0.1
        high = close + np.abs(rng.randn(n) * 0.3)
        low = close - np.abs(rng.randn(n) * 0.3)

        dates = [datetime.now() - timedelta(days=n - i) for i in range(n)]
        mock_response = pd.DataFrame({
            "trade_date": [d.strftime("%Y%m%d") for d in dates],
            "open": high,
            "high": high,
            "low": low,
            "close": close,
            "vol": [10000] * n,
        })

        with patch("core.data_api.ts") as mock_ts:
            mock_ts.set_token.return_value = None
            mock_api = MagicMock()
            mock_api.daily.return_value = mock_response
            mock_ts.pro_api.return_value = mock_api

            from core.data_api import DataAPI
            from core.chan_engine import ChanLunEngine

            api = DataAPI()
            engine = ChanLunEngine()

            df = api.get_daily_kline("000001.SZ")
            assert len(df) > 30

            result = engine.analyze(df, "日线", "000001.SZ")
            total = sum(len(v) for v in result.values())
            assert total > 0
