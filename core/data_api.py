import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from config.settings import *
from tqdm import tqdm
import time

class DataAPI:
    def __init__(self):
        ts.set_token(TUSHARE_TOKEN)
        self.pro = ts.pro_api()

    def get_daily_kline(self, code):
        print(f"[拉取] {code} 日线数据...")

        end = datetime.now()
        start = end - timedelta(days=HISTORY_DAYS)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # 模拟进度条（Tushare 本身不支持流式，给你视觉反馈）
        for _ in tqdm(range(10), desc=f"拉取 {code}"):
            time.sleep(0.05)

        try:
            df = self.pro.daily(
                ts_code=code,
                start_date=start_str,
                end_date=end_str,
                fields="trade_date,open,high,low,close,vol"
            )
        except Exception as e:
            print(f"[ERR] {code} 拉取失败: {e}")
            return pd.DataFrame(columns=["date","open","high","low","close","volume"])

        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date").dropna().reset_index(drop=True)

        print(f"[OK] {code} 拉取完成：{len(df)} 根K线")
        return df

    def build_kline(self, df, level):
        if df.empty:
            return pd.DataFrame()

        rule_map = {"周线": "W", "月线": "ME"}
        if level not in rule_map:
            return df

        for _ in tqdm(range(5), desc=f"合成 {level}"):
            time.sleep(0.02)

        try:
            df = df.set_index("date")
            res = df.resample(rule_map[level]).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum"
            }).dropna().reset_index()
            return res
        except:
            return pd.DataFrame()