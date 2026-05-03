"""
Unit tests for ChanLunEngine – the core Chan-theory analysis logic.

Covers every public method: get_fx_daily, get_bi_daily, get_xd_daily,
get_zhongshu_daily, get_standard_chan_signals_daily, add_indicators,
check_buy, check_sell, and the top-level analyze pipeline.
"""

import pytest
import numpy as np
import pandas as pd

from tests.conftest import (
    make_ohlc_df,
    make_indicator_df,
    build_bi_list_example,
    build_zhongshu_list_example,
)


# ====================================================================
# get_fx_daily  (分型)
# ====================================================================

@pytest.mark.unit
class TestGetFxDaily:
    def test_single_top(self, engine):
        high = [10, 12, 10, 10, 10]
        low = [8, 9, 8, 8, 8]
        assert engine.get_fx_daily(high, low) == [(1, "顶")]

    def test_single_bottom(self, engine):
        high = [10, 10, 10, 10, 10]
        low = [8, 6, 8, 8, 8]
        assert engine.get_fx_daily(high, low) == [(1, "底")]

    def test_alternating(self, engine):
        high = [10, 12, 10, 12, 10, 12, 10]
        low = [8, 9, 6, 9, 6, 9, 8]
        assert engine.get_fx_daily(high, low) == [
            (1, "顶"), (2, "底"), (3, "顶"), (4, "底"), (5, "顶"),
        ]

    def test_no_pattern_monotonic_up(self, engine):
        high = [10, 11, 12, 13, 14]
        low = [8, 9, 10, 11, 12]
        assert engine.get_fx_daily(high, low) == []

    def test_no_pattern_monotonic_down(self, engine):
        high = [14, 13, 12, 11, 10]
        low = [12, 11, 10, 9, 8]
        assert engine.get_fx_daily(high, low) == []

    def test_only_two_bars(self, engine):
        assert engine.get_fx_daily([10, 12], [8, 9]) == []
        assert engine.get_fx_daily([10], [8]) == []

    def test_flat_no_fractal(self, engine):
        high = [10, 10, 10, 10, 10]
        low = [8, 8, 8, 8, 8]
        assert engine.get_fx_daily(high, low) == []

    def test_consecutive_tops(self, engine):
        """Plateau-like pattern – each peak counts if neighbours are lower."""
        high = [10, 12, 12, 12, 10]
        low = [8, 9, 9, 9, 8]
        # idx 1: high[0]=10 < 12, high[2]=12 > 12? No. So not a top.
        # idx 2: high[1]=12 < 12? No. Not a top.
        # idx 3: high[2]=12 < 12? No. Not a top.
        assert engine.get_fx_daily(high, low) == []

    def test_edge_peak_at_ends_ignored(self, engine):
        """First and last bars can never be fractals (need neighbour on each side)."""
        high = [15, 10, 12, 10, 15]
        low = [12, 8, 9, 8, 12]
        # i=0 excluded, i=1: 15>10 and 10<12? Actually 10<12 is True but 15>10 is True...
        # Wait: high[0]=15, high[1]=10, high[2]=12. 15 < 10? No. So not a top.
        # low[0]=12, low[1]=8, low[2]=9. 12 > 8 < 9? Yes → bottom at 1.
        # i=2: high[1]=10, high[2]=12, high[3]=10. 10<12>10 → top at 2.
        # i=3: high[2]=12, high[3]=10, high[4]=15. 12<10? No.
        # low[2]=9, low[3]=8, low[4]=12. 9>8<12 → bottom at 3.
        # i=4 excluded
        assert engine.get_fx_daily(high, low) == [(1, "底"), (2, "顶"), (3, "底")]


# ====================================================================
# get_bi_daily  (笔)
# ====================================================================

@pytest.mark.unit
class TestGetBiDaily:
    def test_basic_two_strokes(self, engine):
        fx = [(2, "顶"), (5, "底"), (8, "顶")]
        high = [10, 11, 12, 11, 10, 9, 10, 11, 12]
        low = [8, 9, 9, 8, 7, 6, 7, 8, 9]
        result = engine.get_bi_daily(fx, high, low)
        assert len(result) == 2
        assert result[0] == {"s": 2, "e": 5, "dir": "down", "high": 12, "low": 6}
        assert result[1] == {"s": 5, "e": 8, "dir": "up", "high": 12, "low": 6}

    def test_less_than_two_fx(self, engine):
        assert engine.get_bi_daily([(3, "顶")], [10, 11, 12, 11, 10], [8, 9, 9, 8, 8]) == []
        assert engine.get_bi_daily([], [10, 11, 12], [8, 9, 9]) == []

    def test_consecutive_same_type_skipped(self, engine):
        """Two tops in a row – second is ignored, only top→bottom forms a stroke."""
        fx = [(2, "顶"), (3, "顶"), (5, "底")]
        high = [10, 11, 12, 12, 10, 9, 9]
        low = [8, 9, 9, 8, 7, 6, 6]
        result = engine.get_bi_daily(fx, high, low)
        assert len(result) == 1
        assert result[0]["dir"] == "down"
        assert result[0]["s"] == 2
        assert result[0]["e"] == 5

    def test_adjacent_indices_rejected(self, engine):
        """idx gap must be > 1, otherwise no stroke."""
        fx = [(3, "顶"), (4, "底")]
        high = [10, 11, 11, 12, 10, 9]
        low = [8, 9, 9, 9, 7, 6]
        assert engine.get_bi_daily(fx, high, low) == []

    def test_bottom_then_top(self, engine):
        fx = [(1, "底"), (4, "顶")]
        high = [10, 9, 10, 11, 12, 11]
        low = [8, 6, 7, 8, 9, 8]
        result = engine.get_bi_daily(fx, high, low)
        assert len(result) == 1
        assert result[0] == {"s": 1, "e": 4, "dir": "up", "high": 12, "low": 6}


# ====================================================================
# get_xd_daily  (线段)
# ====================================================================

@pytest.mark.unit
class TestGetXdDaily:
    def test_four_strokes_produce_three_segments(self, engine):
        bi = build_bi_list_example()  # up, down, up, down
        result = engine.get_xd_daily(bi)
        assert len(result) == 3
        assert result[0]["dir"] == "down"
        assert result[1]["dir"] == "up"
        assert result[2]["dir"] == "down"

    def test_less_than_three_bi(self, engine):
        bi = [
            {"s": 0, "e": 5, "dir": "up", "high": 15, "low": 10},
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 8},
        ]
        assert engine.get_xd_daily(bi) == []

    def test_all_same_direction(self, engine):
        """Three strokes all up → one segment covering all."""
        bi = [
            {"s": 0, "e": 5, "dir": "up", "high": 12, "low": 10},
            {"s": 5, "e": 10, "dir": "up", "high": 14, "low": 11},
            {"s": 10, "e": 15, "dir": "up", "high": 16, "low": 12},
        ]
        result = engine.get_xd_daily(bi)
        assert len(result) == 1
        assert result[0]["dir"] == "up"
        assert result[0]["high"] == 16  # max of all
        assert result[0]["low"] == 10   # min of all
        assert result[0]["s"] == 0
        assert result[0]["e"] == 15

    def test_last_segment_appended(self, engine):
        """Ensure the final direction change produces a trailing segment."""
        bi = [
            {"s": 0, "e": 5, "dir": "up", "high": 15, "low": 10},
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 8},
            {"s": 10, "e": 15, "dir": "up", "high": 18, "low": 8},
        ]
        result = engine.get_xd_daily(bi)
        assert len(result) >= 1
        # last segment should cover through the final stroke
        assert result[-1]["e"] == 15


# ====================================================================
# get_zhongshu_daily  (中枢)
# ====================================================================

@pytest.mark.unit
class TestGetZhongshuDaily:
    def test_overlapping_segments(self, engine):
        xd = [
            {"s": 0, "e": 5, "dir": "up", "high": 20, "low": 10},
            {"s": 5, "e": 10, "dir": "down", "high": 18, "low": 12},
            {"s": 10, "e": 15, "dir": "up", "high": 19, "low": 11},
        ]
        result = engine.get_zhongshu_daily(xd)
        assert len(result) == 1
        assert result[0]["zg"] == 18   # min(20,18,19)
        assert result[0]["zd"] == 12   # max(10,12,11)
        assert result[0]["mid"] == 15.0

    def test_no_overlap(self, engine):
        """Segments don't overlap → no zhongshu."""
        xd = [
            {"s": 0, "e": 5, "dir": "up", "high": 10, "low": 8},
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 14},
            {"s": 10, "e": 15, "dir": "up", "high": 20, "low": 18},
        ]
        # zg = min(10,15,20) = 10, zd = max(8,14,18) = 18 → zg < zd → no zhongshu
        assert engine.get_zhongshu_daily(xd) == []

    def test_marginally_overlapping(self, engine):
        """zg > zd + 0.01 required – just barely overlapping may not count."""
        xd = [
            {"s": 0, "e": 5, "dir": "up", "high": 10.0, "low": 5.0},
            {"s": 5, "e": 10, "dir": "down", "high": 9.0, "low": 8.0},
            {"s": 10, "e": 15, "dir": "up", "high": 10.0, "low": 7.0},
        ]
        # zg = min(10,9,10) = 9.0, zd = max(5,8,7) = 8.0
        # zg > zd + 0.01?  9.0 > 8.01? Yes → zhongshu
        assert len(engine.get_zhongshu_daily(xd)) == 1

        xd_tight = [
            {"s": 0, "e": 5, "dir": "up", "high": 8.005, "low": 5.0},
            {"s": 5, "e": 10, "dir": "down", "high": 8.005, "low": 8.0},
            {"s": 10, "e": 15, "dir": "up", "high": 10.0, "low": 8.0},
        ]
        # zg = min(8.005, 8.005, 10.0) = 8.005, zd = max(5.0, 8.0, 8.0) = 8.0
        # zg > zd + 0.01? 8.005 > 8.01? No → no zhongshu
        assert engine.get_zhongshu_daily(xd_tight) == []

    def test_less_than_three_xd(self, engine):
        assert engine.get_zhongshu_daily([]) == []
        assert engine.get_zhongshu_daily([{"s": 0, "e": 5, "dir": "up", "high": 10, "low": 5}]) == []

    def test_multiple_zhongshu(self, engine):
        """Four overlapping segments → two zhongshu (sliding window of 3)."""
        xd = [
            {"s": 0, "e": 5, "dir": "up", "high": 20, "low": 10},
            {"s": 5, "e": 10, "dir": "down", "high": 18, "low": 12},
            {"s": 10, "e": 15, "dir": "up", "high": 19, "low": 11},
            {"s": 15, "e": 20, "dir": "down", "high": 17, "low": 13},
        ]
        result = engine.get_zhongshu_daily(xd)
        assert len(result) == 2
        assert result[0]["end_idx"] == 2
        assert result[1]["end_idx"] == 3


# ====================================================================
# get_standard_chan_signals_daily  (买卖点)
# ====================================================================

@pytest.mark.unit
class TestGetStandardChanSignalsDaily:
    def _make_dates_closes(self, n=25):
        dates = [f"2024-01-{d:02d}" for d in range(1, n + 1)]
        closes = [10.0] * n
        # Set specific closes at segment-end indices to trigger signals:
        closes[10] = 8.0   # seg0 end (down):  low=8  → 二买
        closes[15] = 18.0  # seg1 end (up):    high=18 → 一卖
        closes[20] = 5.0   # seg2 end (down):  low=5   → 一买
        return dates, closes

    def test_buy_signals(self, engine):
        xd = build_bi_list_example()
        xd_for_sig = [
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 8},
            {"s": 10, "e": 15, "dir": "up", "high": 18, "low": 8},
            {"s": 15, "e": 20, "dir": "down", "high": 18, "low": 5},
        ]
        zs = build_zhongshu_list_example()
        dates, closes = self._make_dates_closes()
        buy, sell = engine.get_standard_chan_signals_daily(xd_for_sig, zs, dates, closes)

        buy_types = {b[3] for b in buy}
        assert "一买" in buy_types
        assert "二买" in buy_types

    def test_sell_signals(self, engine):
        xd = build_bi_list_example()
        xd_for_sig = [
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 8},
            {"s": 10, "e": 15, "dir": "up", "high": 18, "low": 8},
            {"s": 15, "e": 20, "dir": "down", "high": 18, "low": 5},
        ]
        zs = build_zhongshu_list_example()
        dates, closes = self._make_dates_closes()
        buy, sell = engine.get_standard_chan_signals_daily(xd_for_sig, zs, dates, closes)

        sell_types = {s[3] for s in sell}
        assert "一卖" in sell_types

    def test_no_zhongshu_no_signals(self, engine):
        xd = build_bi_list_example()[:3]
        xd_for_sig = [
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 8},
            {"s": 10, "e": 15, "dir": "up", "high": 18, "low": 8},
            {"s": 15, "e": 20, "dir": "down", "high": 18, "low": 5},
        ]
        dates = [f"2024-01-{d:02d}" for d in range(1, 25)]
        closes = [10.0] * 24
        buy, sell = engine.get_standard_chan_signals_daily(xd_for_sig, [], dates, closes)
        assert buy == []
        assert sell == []

    def test_used_set_prevents_duplicate(self, engine):
        """Same index should not produce two signals."""
        xd = build_bi_list_example()
        # Two segments ending at same index
        xd_for_sig = [
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 3},
            {"s": 5, "e": 10, "dir": "down", "high": 15, "low": 3},
        ]
        zs = [{"zg": 15, "zd": 8, "mid": 11.5, "end_idx": 0}]
        dates, closes = self._make_dates_closes()
        closes[10] = 3.0
        buy, sell = engine.get_standard_chan_signals_daily(xd_for_sig, zs, dates, closes)
        assert len(buy) <= 1

    def test_idx_out_of_bounds_skipped(self, engine):
        xd = [
            {"s": 0, "e": 999, "dir": "down", "high": 15, "low": 3},
        ]
        zs = [{"zg": 15, "zd": 8, "mid": 11.5, "end_idx": 0}]
        dates = [f"2024-01-{d:02d}" for d in range(1, 25)]
        closes = [10.0] * 24
        buy, sell = engine.get_standard_chan_signals_daily(xd, zs, dates, closes)
        assert buy == []
        assert sell == []


# ====================================================================
# add_indicators
# ====================================================================

@pytest.mark.unit
class TestAddIndicators:
    def test_columns_exist(self, engine, basic_ohlc):
        df = engine.add_indicators(basic_ohlc.copy())
        for col in ["dif", "dea", "k", "d", "j", "bolu", "bold", "bias"]:
            assert col in df.columns

    def test_shape_preserved(self, engine, basic_ohlc):
        df = engine.add_indicators(basic_ohlc.copy())
        assert len(df) == len(basic_ohlc)

    def test_input_not_mutated(self, engine, basic_ohlc):
        original_cols = set(basic_ohlc.columns)
        engine.add_indicators(basic_ohlc.copy())
        assert set(basic_ohlc.columns) == original_cols

    def test_indicators_not_all_nan(self, engine, basic_ohlc):
        """Edge values from convolution may be off, but interior should be valid."""
        df = engine.add_indicators(basic_ohlc.copy())
        mid = len(df) // 2
        assert not np.isnan(df["dif"].iat[mid])
        assert not np.isnan(df["k"].iat[mid])
        assert not np.isnan(df["bolu"].iat[mid])
        assert not np.isnan(df["bias"].iat[mid])

    def test_empty_df(self, engine):
        """Empty DataFrame raises ValueError from np.convolve – acceptable behaviour."""
        df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        with pytest.raises(ValueError):
            engine.add_indicators(df)


# ====================================================================
# check_buy / check_sell
# ====================================================================

@pytest.mark.unit
class TestCheckBuy:
    def test_all_four_pass(self, engine):
        """dif > dea, k > d and j < 30, close <= bold*1.03, bias < -2.5"""
        df = make_indicator_df(
            close=[10], high=[11], low=[9],
            dif=[1.0], dea=[0.5],
            k=[20], d=[15], j=[25],  # j = 3*k-2*d → 30, wait j<30... let me compute
            bolu=[12], bold=[10],
            bias=[-3.0],
        )
        ok, names, cnt = engine.check_buy(df, 0)
        assert ok is True
        assert cnt == 4
        assert "MACD" in names and "KDJ" in names and "BOLL" in names and "BIAS" in names

    def test_three_pass(self, engine):
        df = make_indicator_df(
            close=[10], high=[11], low=[9],
            dif=[1.0], dea=[0.5],    # MACD ✓
            k=[20], d=[15], j=[25],  # KDJ ✓  (k>d, j<30)
            bolu=[12], bold=[10],    # BOLL ✓ (close 10 <= 10*1.03=10.3)
            bias=[0.0],              # BIAS ✗
        )
        ok, names, cnt = engine.check_buy(df, 0)
        assert ok is True
        assert cnt == 3

    def test_two_pass(self, engine):
        df = make_indicator_df(
            close=[10], high=[11], low=[9],
            dif=[1.0], dea=[0.5],    # MACD ✓
            k=[20], d=[15], j=[25],  # KDJ ✓
            bolu=[12], bold=[9],     # BOLL ✗ (close 10 > 9*1.03=9.27)
            bias=[0.0],              # BIAS ✗
        )
        ok, names, cnt = engine.check_buy(df, 0)
        assert ok is True   # >= 2 still returns True
        assert cnt == 2

    def test_one_pass(self, engine):
        df = make_indicator_df(
            close=[10], high=[11], low=[9],
            dif=[1.0], dea=[0.5],    # MACD ✓
            k=[80], d=[70], j=[95],  # KDJ ✗ (j >= 30)
            bolu=[12], bold=[9],     # BOLL ✗
            bias=[0.0],              # BIAS ✗
        )
        ok, names, cnt = engine.check_buy(df, 0)
        assert ok is False
        assert cnt == 1

    def test_none_pass(self, engine):
        df = make_indicator_df(
            close=[10], high=[11], low=[9],
            dif=[0.5], dea=[1.0],    # MACD ✗
            k=[80], d=[70], j=[95],  # KDJ ✗
            bolu=[12], bold=[9],     # BOLL ✗
            bias=[0.0],              # BIAS ✗
        )
        ok, names, cnt = engine.check_buy(df, 0)
        assert ok is False
        assert cnt == 0


@pytest.mark.unit
class TestCheckSell:
    def test_all_four_pass(self, engine):
        df = make_indicator_df(
            close=[15], high=[16], low=[14],
            dif=[0.5], dea=[1.0],    # MACD ✓ (dif < dea)
            k=[80], d=[70], j=[95],  # KDJ ✓ (k < d? No. Let me fix)
            bolu=[14], bold=[10],
            bias=[3.0],
        )
        # k < d for sell, so need k < d
        df["k"] = [65]
        df["d"] = [70]
        df["j"] = [75]  # j > 70 ✓
        ok, names, cnt = engine.check_sell(df, 0)
        assert ok is True
        assert cnt == 4
        for tag in ["MACD", "KDJ", "BOLL", "BIAS"]:
            assert tag in names

    def test_two_pass_reference(self, engine):
        df = make_indicator_df(
            close=[15], high=[16], low=[14],
            dif=[0.5], dea=[1.0],     # MACD ✓
            k=[65], d=[70], j=[75],   # KDJ ✓
            bolu=[17], bold=[10],     # BOLL ✗ (close 15 < 17*0.97=16.49)
            bias=[0.0],               # BIAS ✗
        )
        ok, names, cnt = engine.check_sell(df, 0)
        assert ok is True
        assert cnt == 2

    def test_exception_returns_false(self, engine):
        """Index out of range triggers except → (False, '', 0)."""
        df = make_indicator_df(
            close=[10], high=[11], low=[9],
            dif=[1.0], dea=[0.5],
            k=[20], d=[15], j=[25],
            bolu=[12], bold=[10],
            bias=[-3.0],
        )
        ok, names, cnt = engine.check_sell(df, 999)
        assert ok is False
        assert cnt == 0


# ====================================================================
# analyze  (full pipeline)
# ====================================================================

@pytest.mark.unit
class TestAnalyze:
    def test_insufficient_data(self, engine):
        df = make_ohlc_df(
            high_seq=[10, 12, 10] * 5,
            low_seq=[8, 9, 8] * 5,
            n_dates=15,
        )
        result = engine.analyze(df, "日线", "TEST")
        for key in ["accurate_buy", "accurate_sell", "normal_buy", "normal_sell"]:
            assert result[key] == []

    def test_result_structure(self, engine, basic_ohlc):
        result = engine.analyze(basic_ohlc, "日线", "TEST")
        assert isinstance(result, dict)
        for key in ["accurate_buy", "accurate_sell", "normal_buy", "normal_sell"]:
            assert key in result
            assert isinstance(result[key], list)

    def test_signal_item_format(self, engine, basic_ohlc):
        result = engine.analyze(basic_ohlc, "日线", "TEST")
        all_signals = (result["accurate_buy"] + result["accurate_sell"] +
                       result["normal_buy"] + result["normal_sell"])
        for item in all_signals:
            assert "time" in item
            assert "price" in item
            assert "type" in item
            assert "indicators" in item
            assert "[日线]" in item["type"]

    def test_long_series_produces_some_signals(self, engine, long_ohlc):
        """200-bar multi-cycle sine wave should produce at least some signals."""
        result = engine.analyze(long_ohlc, "日线", "TEST")
        total = (len(result["accurate_buy"]) + len(result["accurate_sell"]) +
                 len(result["normal_buy"]) + len(result["normal_sell"]))
        assert total > 0, "Expected at least a few signals from 200-bar sine data"
