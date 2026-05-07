"""
Tests for MonitorWindow – data transformation (via DataAPI), CSV I/O, and signal rendering.
"""

import pytest
import os
import csv
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_daily_df(dates=None):
    """Minimal daily OHLC DataFrame for resample tests."""
    if dates is None:
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
    n = len(dates)
    return pd.DataFrame({
        "date": dates,
        "open": np.linspace(10, 12, n),
        "high": np.linspace(11, 13, n),
        "low": np.linspace(9, 11, n),
        "close": np.linspace(10.5, 12.5, n),
        "volume": [1000] * n,
    })


def _sample_signals():
    """Return a result dict that mimics ChanLunEngine.analyze output per period."""
    return {
        "accurate_buy": [
            {"time": "2024-03-15", "price": 9.50, "type": "[日线]一买",
             "indicators": "MACD,KDJ,BOLL"},
        ],
        "accurate_sell": [
            {"time": "2024-06-20", "price": 15.20, "type": "[日线]一卖",
             "indicators": "MACD,KDJ,BIAS"},
        ],
        "normal_buy": [
            {"time": "2024-05-10", "price": 10.80, "type": "[日线]二买",
             "indicators": "MACD,KDJ"},
        ],
        "normal_sell": [],
    }


def _all_res(signals=None):
    """Wrap signals into the all_res dict {period: result} expected by render()."""
    return {"日线": signals or _sample_signals()}


# ---------------------------------------------------------------------------
# DataAPI.build_kline  (resample moved to DataAPI)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBuildKline:
    def test_weekly_reduces_rows(self):
        from core.data_api import DataAPI
        api = DataAPI()
        df = _make_daily_df()
        result = api.build_kline(df, "周线")
        assert len(result) < len(df)
        assert len(result) >= 4

    def test_monthly_reduces_rows(self):
        from core.data_api import DataAPI
        api = DataAPI()
        df = _make_daily_df(pd.date_range("2024-01-01", periods=90, freq="D"))
        result = api.build_kline(df, "月线")
        assert len(result) < len(df)
        assert 2 <= len(result) <= 4

    def test_weekly_preserves_ohlc_columns(self):
        from core.data_api import DataAPI
        api = DataAPI()
        df = _make_daily_df()
        result = api.build_kline(df, "周线")
        for col in ["open", "high", "low", "close"]:
            assert col in result.columns

    def test_empty_df_returns_empty(self):
        from core.data_api import DataAPI
        api = DataAPI()
        result = api.build_kline(pd.DataFrame(), "周线")
        assert result.empty


# ---------------------------------------------------------------------------
# CSV  operations
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCsvOperations:
    @pytest.fixture
    def csv_path(self, tmp_path):
        return str(tmp_path / "test_signals.csv")

    def test_init_csv_creates_file_with_header(self, csv_path):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.csv_path = csv_path
        mw._seen = set()
        mw.init_csv()

        assert os.path.exists(csv_path)
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["股票代码", "级别类型", "日期", "价格", "确认指标", "记录时间"]

    def test_init_csv_does_not_overwrite(self, csv_path):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.csv_path = csv_path
        mw._seen = set()
        mw.init_csv()

        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["000001.SZ", "日线", "2024-01-01", "10.0", "MACD", "now"])

        mw.init_csv()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 2

    def test_save_csv_appends_row(self, csv_path):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.csv_path = csv_path
        mw._seen = set()
        mw.init_csv()

        row = ["000001.SZ", "[日线]一买", "2024-03-15", "9.50", "MACD,KDJ", "2024-03-15 10-30-00"]
        mw.save_csv(row)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 2
            assert rows[1] == row

    def test_save_csv_skips_duplicate(self, csv_path):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.csv_path = csv_path
        mw._seen = set()
        mw.init_csv()

        row = ["000001.SZ", "[日线]一买", "2024-03-15", "9.50", "MACD,KDJ", "2024-03-15 10-30-00"]
        mw.save_csv(row)
        mw.save_csv(row)  # duplicate — should be skipped

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 2  # header + 1 row, not 3

    def test_init_csv_loads_existing_keys(self, csv_path):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.csv_path = csv_path
        mw._seen = set()
        mw.init_csv()

        mw.save_csv(["000001.SZ", "[日线]一买", "2024-03-15", "9.50", "MACD", "now"])

        mw2 = MonitorWindow.__new__(MonitorWindow)
        mw2.csv_path = csv_path
        mw2._seen = set()
        mw2.init_csv()
        assert ("000001.SZ", "[日线]一买", "2024-03-15") in mw2._seen


# ---------------------------------------------------------------------------
# render  (signal formatting + GUI scheduling)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRender:
    def test_render_schedules_correct_number_of_inserts(self):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.root = MagicMock()
        mw.buy_list = MagicMock()
        mw.sell_list = MagicMock()
        mw.save_csv = MagicMock()

        mw.render("TEST", _all_res())
        assert mw.root.after.call_count == 3

    def test_render_accurate_buy_uses_add_buy(self, monkeypatch):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.root = MagicMock()
        mw.buy_list = MagicMock()
        mw.sell_list = MagicMock()
        mw.save_csv = MagicMock()

        mw.add_buy = MagicMock()
        mw.add_sell = MagicMock()

        def fake_after(ms, cb, *args):
            cb(*args)
        mw.root.after = fake_after

        mw.render("TEST", _all_res())

        assert mw.add_buy.call_count == 2
        assert mw.add_sell.call_count == 1

    def test_render_line_format(self, monkeypatch):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.root = MagicMock()
        mw.buy_list = MagicMock()
        mw.sell_list = MagicMock()
        mw.save_csv = MagicMock()

        captured_lines = []
        def fake_after(ms, cb, *args):
            captured_lines.append(args[0])
        mw.root.after = fake_after

        mw.render("TEST", _all_res())

        assert any("[精准]" in line and "TEST" in line for line in captured_lines)
        assert any("一买" in line for line in captured_lines)


# ---------------------------------------------------------------------------
# cross-timeframe confirmation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCrossTimeframe:
    def test_daily_confirmed_by_weekly(self):
        from ui.monitor_window import MonitorWindow
        date_sets = {
            "日线": {pd.Timestamp("2024-03-15").date()},
            "周线": {pd.Timestamp("2024-03-14").date()},
            "月线": set(),
        }
        assert MonitorWindow._is_confirmed("2024-03-15", "日线", date_sets) is True

    def test_daily_not_confirmed_if_too_far(self):
        from ui.monitor_window import MonitorWindow
        date_sets = {
            "日线": {pd.Timestamp("2024-03-15").date()},
            "周线": {pd.Timestamp("2024-03-25").date()},
            "月线": set(),
        }
        assert MonitorWindow._is_confirmed("2024-03-15", "日线", date_sets) is False

    def test_weekly_confirmed_by_monthly(self):
        from ui.monitor_window import MonitorWindow
        date_sets = {
            "日线": set(),
            "周线": {pd.Timestamp("2024-03-14").date()},
            "月线": {pd.Timestamp("2024-03-12").date()},
        }
        assert MonitorWindow._is_confirmed("2024-03-14", "周线", date_sets) is True

    def test_monthly_never_confirmed(self):
        from ui.monitor_window import MonitorWindow
        date_sets = {
            "日线": {pd.Timestamp("2024-03-15").date()},
            "周线": {pd.Timestamp("2024-03-14").date()},
            "月线": {pd.Timestamp("2024-03-13").date()},
        }
        assert MonitorWindow._is_confirmed("2024-03-13", "月线", date_sets) is False
