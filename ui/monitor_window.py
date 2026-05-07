import tkinter as tk
import threading
import csv
import os
from datetime import datetime, timedelta
import pandas as pd
from core.data_api import DataAPI
from core.chan_engine import ChanLunEngine

CONFIRM_WINDOW_DAYS = 5


class MonitorWindow:
    def __init__(self, codes):
        self.codes = codes
        self.api = DataAPI()
        self.chan = ChanLunEngine()
        self.csv_path = "trading_signals.csv"
        self._seen = set()
        self.init_csv()

        self.root = tk.Tk()
        self.root.title("缠论精准系统【先≥3指标｜后=2指标】")
        self.root.geometry("1400x800")

        # 买点
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=1, padx=5, pady=5)
        tk.Label(left, text="买点【绿色≥3指标｜白色=2指标｜青色=跨级别确认】", font=("黑体",14)).pack()
        self.buy_list = tk.Listbox(left, font=("黑体",11))
        self.buy_list.pack(fill=tk.BOTH, expand=1)

        # 卖点
        right = tk.Frame(self.root)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1, padx=5, pady=5)
        tk.Label(right, text="卖点【红色≥3指标｜白色=2指标｜橙色=跨级别确认】", font=("黑体",14)).pack()
        self.sell_list = tk.Listbox(right, font=("黑体",11))
        self.sell_list.pack(fill=tk.BOTH, expand=1)

    def init_csv(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["股票代码","级别类型","日期","价格","确认指标","记录时间"])
        else:
            with open(self.csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 3:
                        self._seen.add((row[0], row[1], self._date_key(row[2])))

    @staticmethod
    def _date_key(d):
        return str(d)[:10]

    def save_csv(self, row):
        key = (row[0], row[1], self._date_key(row[2]))
        if key in self._seen:
            return
        self._seen.add(key)
        row[2] = self._date_key(row[2])
        with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(row)

    def add_buy(self, line, data, is_acc, confirmed=False):
        self.buy_list.insert(tk.END, line)
        if confirmed:
            self.buy_list.itemconfig(tk.END, bg="#cceeff")
        elif is_acc:
            self.buy_list.itemconfig(tk.END, bg="#e6ffe6")
        self.save_csv(data)

    def add_sell(self, line, data, is_acc, confirmed=False):
        self.sell_list.insert(tk.END, line)
        if confirmed:
            self.sell_list.itemconfig(tk.END, bg="#ffe6cc")
        elif is_acc:
            self.sell_list.itemconfig(tk.END, bg="#ffe6e6")
        self.save_csv(data)

    def render(self, code, all_res):
        now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")

        # 收集各时间段的信号日期，用于跨级别确认
        buy_dates = {"日线": set(), "周线": set(), "月线": set()}
        sell_dates = {"日线": set(), "周线": set(), "月线": set()}

        for period, res in all_res.items():
            for b in res.get("accurate_buy", []) + res.get("normal_buy", []):
                buy_dates[period].add(self._parse_date(b["time"]))
            for s in res.get("accurate_sell", []) + res.get("normal_sell", []):
                sell_dates[period].add(self._parse_date(s["time"]))

        for period, res in all_res.items():
            for b in res["accurate_buy"]:
                date_str = self._date_key(b["time"])
                confirmed = self._is_confirmed(b["time"], period, buy_dates)
                tag = "[强确认]" if confirmed else "[精准]"
                line = f"{tag} [{code}] {b['type']} | {date_str} | 价格{b['price']:.2f} | {b['indicators']}"
                data = [code, b["type"], b["time"], b["price"], b["indicators"], now]
                self.root.after(0, self.add_buy, line, data, True, confirmed)

            for s in res["accurate_sell"]:
                date_str = self._date_key(s["time"])
                confirmed = self._is_confirmed(s["time"], period, sell_dates)
                tag = "[强确认]" if confirmed else "[精准]"
                line = f"{tag} [{code}] {s['type']} | {date_str} | 价格{s['price']:.2f} | {s['indicators']}"
                data = [code, s["type"], s["time"], s["price"], s["indicators"], now]
                self.root.after(0, self.add_sell, line, data, True, confirmed)

            for b in res["normal_buy"]:
                date_str = self._date_key(b["time"])
                confirmed = self._is_confirmed(b["time"], period, buy_dates)
                tag = "[强参考]" if confirmed else "[参考]"
                line = f"{tag} [{code}] {b['type']} | {date_str} | 价格{b['price']:.2f} | {b['indicators']}"
                data = [code, b["type"], b["time"], b["price"], b["indicators"], now]
                self.root.after(0, self.add_buy, line, data, False, confirmed)

            for s in res["normal_sell"]:
                date_str = self._date_key(s["time"])
                confirmed = self._is_confirmed(s["time"], period, sell_dates)
                tag = "[强参考]" if confirmed else "[参考]"
                line = f"{tag} [{code}] {s['type']} | {date_str} | 价格{s['price']:.2f} | {s['indicators']}"
                data = [code, s["type"], s["time"], s["price"], s["indicators"], now]
                self.root.after(0, self.add_sell, line, data, False, confirmed)

    @staticmethod
    def _parse_date(d):
        try:
            return pd.Timestamp(d).date()
        except Exception:
            return None

    @classmethod
    def _is_confirmed(cls, signal_time, current_period, date_sets):
        d = cls._parse_date(signal_time)
        if d is None:
            return False
        higher = []
        if current_period == "日线":
            higher = ["周线", "月线"]
        elif current_period == "周线":
            higher = ["月线"]
        else:
            return False
        for hp in higher:
            for hd in date_sets.get(hp, set()):
                if hd and abs((d - hd).days) <= CONFIRM_WINDOW_DAYS:
                    return True
        return False

    # 多线程
    def work(self, code):
        try:
            df_day = self.api.get_daily_kline(code)
            if len(df_day) < 30:
                return
            df_wk = self.api.build_kline(df_day, "周线")
            df_mn = self.api.build_kline(df_day, "月线")

            all_res = {}
            for p, d in [("日线", df_day), ("周线", df_wk), ("月线", df_mn)]:
                all_res[p] = self.chan.analyze(d, p, code)

            self.render(code, all_res)
            print(f"[OK] {code} 完成")
        except Exception as e:
            print(f"[ERR] {code} 错误：{e}")

    def run(self):
        for code in self.codes:
            threading.Thread(target=self.work, args=(code,), daemon=True).start()

    def start(self):
        self.root.after(100, self.run)
        self.root.mainloop()