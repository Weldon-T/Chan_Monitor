"""
Integration tests for DataAPI – Tushare data fetching and K-line resampling.

Real Tushare calls are mocked so tests run offline.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# build_kline
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestBuildKline:
    def test_empty_df(self):
        from core.data_api import DataAPI
        api = DataAPI()
        result = api.build_kline(pd.DataFrame(), "周线")
        assert result.empty

    def test_weekly_resample(self):
        from core.data_api import DataAPI
        api = DataAPI()

        dates = pd.date_range("2024-01-01", periods=20, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "open": [10.0 + i * 0.1 for i in range(20)],
            "high": [11.0 + i * 0.1 for i in range(20)],
            "low": [9.0 + i * 0.1 for i in range(20)],
            "close": [10.5 + i * 0.1 for i in range(20)],
            "volume": [1000] * 20,
        })

        result = api.build_kline(df, "周线")
        assert not result.empty
        assert len(result) < 20  # aggregation reduces rows
        assert "date" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns

        # high should be the max within each week
        first_week_high_orig = df[df["date"] < dates[0] + pd.Timedelta(days=7)]["high"].max()
        assert result["high"].iloc[0] == first_week_high_orig

    def test_monthly_resample(self):
        from core.data_api import DataAPI
        api = DataAPI()

        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "open": [10.0] * 60,
            "high": [11.0] * 60,
            "low": [9.0] * 60,
            "close": [10.5] * 60,
            "volume": [1000] * 60,
        })

        result = api.build_kline(df, "月线")
        assert not result.empty
        # 60 days → roughly 2 months
        assert 1 <= len(result) <= 3

    def test_unknown_level_returns_original(self):
        from core.data_api import DataAPI
        api = DataAPI()

        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "open": [10.0] * 5,
            "high": [11.0] * 5,
            "low": [9.0] * 5,
            "close": [10.5] * 5,
            "volume": [1000] * 5,
        })

        result = api.build_kline(df, "日线")
        pd.testing.assert_frame_equal(result, df)

    def test_resample_preserves_ohlc_logic(self):
        """open=first, high=max, low=min, close=last, volume=sum."""
        from core.data_api import DataAPI
        api = DataAPI()

        dates = pd.date_range("2024-01-01", periods=14, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "open": [10, 12, 11, 13, 14, 15, 16] * 2,
            "high": [15, 14, 13, 16, 17, 18, 19] * 2,
            "low": [9, 11, 10, 12, 13, 14, 15] * 2,
            "close": [12, 11, 13, 14, 16, 17, 18] * 2,
            "volume": [100, 200, 300, 400, 500, 600, 700] * 2,
        })

        result = api.build_kline(df, "周线")
        first_row = result.iloc[0]
        first_week = df[df["date"] < dates[0] + pd.Timedelta(days=7)]

        assert first_row["open"] == first_week["open"].iloc[0]
        assert first_row["high"] == first_week["high"].max()
        assert first_row["low"] == first_week["low"].min()
        assert first_row["close"] == first_week["close"].iloc[-1]
        assert first_row["volume"] == first_week["volume"].sum()


# ---------------------------------------------------------------------------
# get_daily_kline  (mocked Tushare)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetDailyKline:
    @pytest.fixture
    def mock_tushare_df(self):
        """Return a DataFrame that looks like Tushare's pro_api.daily() output."""
        dates = pd.date_range(end=datetime.now(), periods=100, freq="D")
        return pd.DataFrame({
            "trade_date": [d.strftime("%Y%m%d") for d in dates],
            "open": np.random.RandomState(0).randn(100).cumsum() + 10,
            "high": np.random.RandomState(1).randn(100).cumsum() + 11,
            "low": np.random.RandomState(2).randn(100).cumsum() + 9,
            "close": np.random.RandomState(3).randn(100).cumsum() + 10,
            "vol": np.random.RandomState(4).randint(1000, 10000, 100),
        })

    def test_returns_dataframe_with_correct_columns(self, mock_tushare_df):
        with patch("core.data_api.ts") as mock_ts:
            mock_ts.set_token.return_value = None
            mock_api = MagicMock()
            mock_api.daily.return_value = mock_tushare_df
            mock_ts.pro_api.return_value = mock_api

            from core.data_api import DataAPI
            api = DataAPI()
            result = api.get_daily_kline("000001.SZ")

            assert isinstance(result, pd.DataFrame)
            for col in ["date", "open", "high", "low", "close", "volume"]:
                assert col in result.columns
            assert len(result) == len(mock_tushare_df)

    def test_date_column_is_datetime(self, mock_tushare_df):
        with patch("core.data_api.ts") as mock_ts:
            mock_ts.set_token.return_value = None
            mock_api = MagicMock()
            mock_api.daily.return_value = mock_tushare_df
            mock_ts.pro_api.return_value = mock_api

            from core.data_api import DataAPI
            api = DataAPI()
            result = api.get_daily_kline("000001.SZ")

            assert pd.api.types.is_datetime64_any_dtype(result["date"])

    def test_sorted_by_date_ascending(self, mock_tushare_df):
        # shuffle to verify sorting
        shuffled = mock_tushare_df.sample(frac=1).reset_index(drop=True)
        with patch("core.data_api.ts") as mock_ts:
            mock_ts.set_token.return_value = None
            mock_api = MagicMock()
            mock_api.daily.return_value = shuffled
            mock_ts.pro_api.return_value = mock_api

            from core.data_api import DataAPI
            api = DataAPI()
            result = api.get_daily_kline("000001.SZ")

            assert result["date"].is_monotonic_increasing

    def test_tushare_exception_returns_empty_df(self):
        with patch("core.data_api.ts") as mock_ts, \
             patch("core.data_api.DataAPI._load_cache", return_value=None):
            mock_ts.set_token.return_value = None
            mock_api = MagicMock()
            mock_api.daily.side_effect = Exception("Network error")
            mock_ts.pro_api.return_value = mock_api

            from core.data_api import DataAPI
            api = DataAPI()
            result = api.get_daily_kline("000001.SZ")

            assert result.empty
            for col in ["date", "open", "high", "low", "close", "volume"]:
                assert col in result.columns

    def test_drops_na_rows(self, mock_tushare_df):
        # inject a NaN row
        dirty = mock_tushare_df.copy()
        dirty.loc[50, "close"] = np.nan
        with patch("core.data_api.ts") as mock_ts:
            mock_ts.set_token.return_value = None
            mock_api = MagicMock()
            mock_api.daily.return_value = dirty
            mock_ts.pro_api.return_value = mock_api

            from core.data_api import DataAPI
            api = DataAPI()
            result = api.get_daily_kline("000001.SZ")

            assert not result.isnull().any().any()
