import tkinter as tk
import threading
import csv
import os
from datetime import datetime
import pandas as pd
from core.data_api import DataAPI
from core.chan_engine import ChanLunEngine

class MonitorWindow:
    def __init__(self, codes):
        self.codes = codes
        self.api = DataAPI()
        self.chan = ChanLunEngine()
        self.csv_path = "trading_signals.csv"
        self.init_csv()

        self.root = tk.Tk()
        self.root.title("缠论精准系统【先≥3指标｜后=2指标】")
        self.root.geometry("1400x800")

        # 买点
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=1, padx=5, pady=5)
        tk.Label(left, text="买点【绿色≥3指标｜白色=2指标】", font=("黑体",14)).pack()
        self.buy_list = tk.Listbox(left, font=("黑体",11))
        self.buy_list.pack(fill=tk.BOTH, expand=1)

        # 卖点
        right = tk.Frame(self.root)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1, padx=5, pady=5)
        tk.Label(right, text="卖点【绿色≥3指标｜白色=2指标】", font=("黑体",14)).pack()
        self.sell_list = tk.Listbox(right, font=("黑体",11))
        self.sell_list.pack(fill=tk.BOTH, expand=1)

    def init_csv(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["股票代码","级别类型","日期","价格","确认指标","记录时间"])

    # ==========================
    # CSV 只存界面显示的条目（核心）
    # ==========================
    def save_csv(self, row):
        with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(row)

    def add_buy(self, line, data, is_acc):
        self.buy_list.insert(tk.END, line)
        if is_acc: self.buy_list.itemconfig(tk.END, bg="#e6ffe6")
        self.save_csv(data)

    def add_sell(self, line, data, is_acc):
        self.sell_list.insert(tk.END, line)
        if is_acc: self.sell_list.itemconfig(tk.END, bg="#ffe6e6")
        self.save_csv(data)

    # 显示顺序：先精准 ≥3，后参考 =2
    def render(self, code, res):
        now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")

        for b in res["accurate_buy"]:
            line = f"[精准] [{code}] {b['type']} | {b['time']} | 价格{b['price']:.2f} | {b['indicators']}"
            data = [code, b["type"], b["time"], b["price"], b["indicators"], now]
            self.root.after(0, self.add_buy, line, data, True)

        for s in res["accurate_sell"]:
            line = f"[精准] [{code}] {s['type']} | {s['time']} | 价格{s['price']:.2f} | {s['indicators']}"
            data = [code, s["type"], s["time"], s["price"], s["indicators"], now]
            self.root.after(0, self.add_sell, line, data, True)

        for b in res["normal_buy"]:
            line = f"[参考] [{code}] {b['type']} | {b['time']} | 价格{b['price']:.2f} | {b['indicators']}"
            data = [code, b["type"], b["time"], b["price"], b["indicators"], now]
            self.root.after(0, self.add_buy, line, data, False)

        for s in res["normal_sell"]:
            line = f"[参考] [{code}] {s['type']} | {s['time']} | 价格{s['price']:.2f} | {s['indicators']}"
            data = [code, s["type"], s["time"], s["price"], s["indicators"], now]
            self.root.after(0, self.add_sell, line, data, False)

    # 正确合成周月线
    def to_weekly(self, df):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        w = df.groupby(df["date"].dt.to_period("W")).agg(
            date=("date","last"), open=("open","first"), high=("high","max"), low=("low","min"), close=("close","last")
        ).reset_index(drop=True)
        w["date"] = w["date"].dt.strftime("%Y-%m-%d")
        return w

    def to_monthly(self, df):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        m = df.groupby(df["date"].dt.to_period("M")).agg(
            date=("date","last"), open=("open","first"), high=("high","max"), low=("low","min"), close=("close","last")
        ).reset_index(drop=True)
        m["date"] = m["date"].dt.strftime("%Y-%m-%d")
        return m

    # 多线程
    def work(self, code):
        try:
            df_day = self.api.get_daily_kline(code)
            if len(df_day) < 30: return
            df_wk = self.to_weekly(df_day)
            df_mn = self.to_monthly(df_day)

            for p, d in [("日线", df_day), ("周线", df_wk), ("月线", df_mn)]:
                res = self.chan.analyze(d, p, code)
                self.render(code, res)

            print(f"✅ {code} 完成")
        except Exception as e:
            print(f"❌ {code} 错误：{e}")

    def run(self):
        for code in self.codes:
            threading.Thread(target=self.work, args=(code,), daemon=True).start()

    def start(self):
        self.root.after(100, self.run)
        self.root.mainloop()