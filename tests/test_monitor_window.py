"""
Tests for MonitorWindow – data transformation, CSV I/O, and signal rendering.

GUI construction is tested minimally (skipped when no display is available).
"""

import pytest
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime
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
    """Return a result dict that mimics ChanLunEngine.analyze output."""
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


# ---------------------------------------------------------------------------
# to_weekly / to_monthly
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestResampleMethods:
    def test_to_weekly_reduces_rows(self):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)  # skip __init__
        df = _make_daily_df()
        result = mw.to_weekly(df)
        assert len(result) < len(df)
        assert len(result) >= 4  # 30 days ≈ 4+ weeks

    def test_to_monthly_reduces_rows(self):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        df = _make_daily_df(pd.date_range("2024-01-01", periods=90, freq="D"))
        result = mw.to_monthly(df)
        assert len(result) < len(df)
        assert 2 <= len(result) <= 4  # 90 days ≈ 3 months

    def test_to_weekly_preserves_ohlc_columns(self):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        df = _make_daily_df()
        result = mw.to_weekly(df)
        for col in ["open", "high", "low", "close"]:
            assert col in result.columns

    def test_to_weekly_date_is_string(self):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        df = _make_daily_df()
        result = mw.to_weekly(df)
        assert isinstance(result["date"].iloc[0], str)

    def test_to_weekly_open_is_first_of_week(self):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        dates = pd.date_range("2024-01-01", periods=14, freq="D")
        df = _make_daily_df(dates)
        # Monday open is low, Friday open is high
        df["open"] = [1, 2, 3, 4, 5, 2, 2, 1, 2, 3, 4, 5, 2, 2]

        result = mw.to_weekly(df)
        first_week_open = result["open"].iloc[0]
        # get the first date that falls in the first ISO week
        first_monday = dates[0]  # 2024-01-01 is Monday
        assert first_week_open == df[df["date"] == first_monday]["open"].values[0]


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
        mw.init_csv()

        # write something after header
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["000001.SZ", "日线", "2024-01-01", "10.0", "MACD", "now"])

        # second init should not delete data
        mw.init_csv()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 2  # header + 1 data row

    def test_save_csv_appends_row(self, csv_path):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.csv_path = csv_path
        mw.init_csv()

        row = ["000001.SZ", "[日线]一买", "2024-03-15", "9.50", "MACD,KDJ", "2024-03-15 10-30-00"]
        mw.save_csv(row)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 2
            assert rows[1] == row


# ---------------------------------------------------------------------------
# render  (signal formatting + GUI scheduling)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRender:
    def test_render_schedules_correct_number_of_inserts(self):
        """render() should call root.after once per signal."""
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.root = MagicMock()
        mw.buy_list = MagicMock()
        mw.sell_list = MagicMock()
        mw.save_csv = MagicMock()

        signals = _sample_signals()
        mw.render("TEST", signals)

        # 1 accurate buy + 1 accurate sell + 1 normal buy = 3 signals
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

        # patch root.after to call the callback immediately
        def fake_after(ms, cb, *args):
            cb(*args)
        mw.root.after = fake_after

        signals = _sample_signals()
        mw.render("TEST", signals)

        assert mw.add_buy.call_count == 2   # 1 accurate + 1 normal
        assert mw.add_sell.call_count == 1  # 1 accurate

    def test_render_line_format(self, monkeypatch):
        from ui.monitor_window import MonitorWindow
        mw = MonitorWindow.__new__(MonitorWindow)
        mw.root = MagicMock()
        mw.buy_list = MagicMock()
        mw.sell_list = MagicMock()
        mw.save_csv = MagicMock()

        captured_lines = []
        def fake_after(ms, cb, *args):
            captured_lines.append(args[0])  # first arg to add_buy/add_sell is the line
        mw.root.after = fake_after

        signals = _sample_signals()
        mw.render("TEST", signals)

        assert any("[精准]" in line and "TEST" in line for line in captured_lines)
        assert any("一买" in line for line in captured_lines)
