import tushare as ts
import pandas as pd
import pickle
import os
import time
from datetime import datetime, timedelta
from config.settings import *

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")


class DataAPI:
    def __init__(self):
        ts.set_token(TUSHARE_TOKEN)
        self.pro = ts.pro_api()

    def _cache_path(self, code):
        return os.path.join(CACHE_DIR, f"{code}.pkl")

    def _load_cache(self, code):
        path = self._cache_path(code)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            age = time.time() - data["ts"]
            if age < REFRESH_INTERVAL:
                return data["df"]
            os.remove(path)
        except Exception:
            pass
        return None

    def _save_cache(self, code, df):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(self._cache_path(code), "wb") as f:
            pickle.dump({"df": df, "ts": time.time()}, f)

    def get_daily_kline(self, code):
        cached = self._load_cache(code)
        if cached is not None:
            print(f"[缓存] {code} 使用缓存数据（{len(cached)} 根K线）")
            return cached

        print(f"[拉取] {code} 日线数据...")

        end = datetime.now()
        start = end - timedelta(days=HISTORY_DAYS)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        last_err = None
        for attempt in range(3):
            try:
                df = self.pro.daily(
                    ts_code=code,
                    start_date=start_str,
                    end_date=end_str,
                    fields="trade_date,open,high,low,close,vol"
                )
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    wait = 2 ** attempt
                    print(f"[RETRY] {code} 第{attempt+1}次重试，等待{wait}秒...")
                    time.sleep(wait)
        else:
            print(f"[ERR] {code} 拉取失败（重试3次）: {last_err}")
            return pd.DataFrame(columns=["date","open","high","low","close","volume"])

        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date").dropna().reset_index(drop=True)

        self._save_cache(code, df)
        print(f"[OK] {code} 拉取完成：{len(df)} 根K线")
        return df

    def build_kline(self, df, level):
        if df.empty:
            return pd.DataFrame()

        rule_map = {"周线": "W", "月线": "ME"}
        if level not in rule_map:
            return df

        try:
            df = df.set_index("date")
            res = df.resample(rule_map[level]).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum"
            }).dropna()

            trading_days = df.index.sort_values()
            adjusted = []
            for d in res.index:
                candidates = trading_days[trading_days <= d]
                adjusted.append(candidates[-1] if len(candidates) > 0 else d)
            res.index = pd.DatetimeIndex(adjusted, name="date")

            return res.reset_index()
        except Exception:
            return pd.DataFrame()