import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_ohlc_df(high_seq, low_seq, close_seq=None, n_dates=None):
    """Build a minimal OHLC DataFrame suitable for ChanLunEngine.

    Parameters
    ----------
    high_seq : list[float]
    low_seq : list[float]
    close_seq : list[float] | None
        If None, close = (high + low) / 2.
    n_dates : int | None
        Number of date rows.  If None, len(high_seq) is used.

    Returns
    -------
    pd.DataFrame  with columns date, open, high, low, close, volume.
    """
    n = n_dates or len(high_seq)
    if close_seq is None:
        close_seq = [(h + l) / 2 for h, l in zip(high_seq, low_seq)]

    dates = [(datetime.now() - timedelta(days=n - i)).strftime("%Y-%m-%d") for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "open": [h for h in high_seq],
        "high": [h for h in high_seq],
        "low": [l for l in low_seq],
        "close": [c for c in close_seq],
        "volume": [10000] * n,
    })


def make_ohlc_df_np(high_arr, low_arr, close_arr=None):
    """Same as make_ohlc_df but accepts numpy arrays."""
    return make_ohlc_df(high_arr.tolist(), low_arr.tolist(),
                        close_arr.tolist() if close_arr is not None else None)


def make_indicator_df(close, high, low, dif, dea, k, d, j, bolu, bold, bias):
    """Build a DataFrame with pre-set indicator columns for check_buy / check_sell testing."""
    n = len(close)
    dates = [(datetime.now() - timedelta(days=n - i)).strftime("%Y-%m-%d") for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "open": high,
        "high": high,
        "low": low,
        "close": close,
        "volume": [10000] * n,
        "dif": dif,
        "dea": dea,
        "k": k,
        "d": d,
        "j": j,
        "bolu": bolu,
        "bold": bold,
        "bias": bias,
    })


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    from core.chan_engine import ChanLunEngine
    return ChanLunEngine()


@pytest.fixture
def basic_ohlc():
    """50-bar gentle sine wave – enough data for the full pipeline."""
    n = 50
    x = np.linspace(0, 4 * np.pi, n)
    close = 10 + np.sin(x) * 3 + np.linspace(0, 2, n)
    high = close + np.abs(np.random.RandomState(42).randn(n) * 0.3)
    low = close - np.abs(np.random.RandomState(42).randn(n) * 0.3)
    return make_ohlc_df_np(high, low, close)


@pytest.fixture
def long_ohlc():
    """200-bar multi-cycle sine wave for e2e tests."""
    n = 200
    rng = np.random.RandomState(99)
    x = np.linspace(0, 8 * np.pi, n)
    close = 10 + np.sin(x) * 4 + np.linspace(0, 6, n) + rng.randn(n) * 0.15
    high = close + np.abs(rng.randn(n) * 0.4)
    low = close - np.abs(rng.randn(n) * 0.4)
    return make_ohlc_df_np(high, low, close)


@pytest.fixture
def ohlc_with_indicators(engine, basic_ohlc):
    """basic_ohlc after add_indicators has run."""
    return engine.add_indicators(basic_ohlc.copy())


# ---------------------------------------------------------------------------
# shared test-data builders for Chan shapes
# ---------------------------------------------------------------------------

def build_bi_list_example():
    """Return a 4-stroke list that produces 3 segments + 1 zhongshu.

    Segments produced (by get_xd_daily):
      0: down 5→10  high=15 low=8
      1: up   10→15 high=18 low=8
      2: down 15→20 high=18 low=5

    Zhongshu: zg=15  zd=8  mid=11.5

    Signals with closes = same as segment low/high:
      seg0(down):  low=8   → 二买 (8 in [8, 11.5))
      seg1(up):    high=18  → 一卖 (18 > 15)
      seg2(down):  low=5   → 一买 (5 < 8)
    """
    return [
        {"s": 0,  "e": 5,  "dir": "up",   "high": 15, "low": 10},
        {"s": 5,  "e": 10, "dir": "down", "high": 15, "low": 8},
        {"s": 10, "e": 15, "dir": "up",   "high": 18, "low": 8},
        {"s": 15, "e": 20, "dir": "down", "high": 18, "low": 5},
    ]


def build_zhongshu_list_example():
    """Return the single zhongshu produced by build_bi_list_example."""
    return [{"zg": 15, "zd": 8, "mid": 11.5, "end_idx": 0,
             "segments": build_bi_list_example()[:3]}]
