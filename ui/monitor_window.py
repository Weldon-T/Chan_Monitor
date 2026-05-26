import tkinter as tk
from tkinter import ttk
import threading
import csv
import os
from datetime import datetime, timedelta
import pandas as pd
from core.data_api import DataAPI
from core.chan_engine import ChanLunEngine

CONFIRM_WINDOW_DAYS = 5

# ---- Design Tokens (dark terminal theme) ----
BG           = "#0D1117"
SURFACE      = "#161B22"
BORDER       = "#30363D"
TEXT         = "#E6EDF3"
TEXT_MUTED   = "#8B949E"
HEADER_BG    = "#010409"
BUY_GREEN    = "#2EA043"
SELL_RED     = "#DA3633"
CONFIRM_BLUE = "#58A6FF"
CONFIRM_AMBER = "#D29922"
ROW_BUY_STRONG    = "#1B3A2A"
ROW_SELL_STRONG   = "#3D1F1F"
ROW_BUY_CONFIRM   = "#1A2E4A"
ROW_SELL_CONFIRM  = "#3D2E0A"
ROW_NORMAL        = "#1C1F26"
ACCENT_SELECTED   = "#1F6FEB"

FONT      = ("Microsoft YaHei", 10)
FONT_BOLD = ("Microsoft YaHei", 10, "bold")
FONT_H1   = ("Microsoft YaHei", 18, "bold")
FONT_H2   = ("Microsoft YaHei", 13, "bold")
FONT_SM   = ("Microsoft YaHei", 9)

COLUMNS = ("股票代码", "日期", "级别", "类型", "价格", "确认指标", "强度")
COL_WIDTHS = [105, 105, 55, 55, 80, 175, 55]
COL_ANCHORS = ["center", "center", "center", "center", "center", "w", "center"]


class MonitorWindow:
    def __init__(self, codes):
        self.codes = codes
        self.api = DataAPI()
        self.chan = ChanLunEngine()
        self.csv_path = "trading_signals.csv"
        self._seen = set()
        self._buy_signals = []
        self._sell_signals = []
        self._threads_done = 0
        self._total_threads = len(codes)
        self.init_csv()
        self._build_ui()

    # ===================================================================
    # CSV (unchanged public interface)
    # ===================================================================

    def init_csv(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(
                    ["股票代码", "级别类型", "日期", "价格", "确认指标", "记录时间"])
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

    # ===================================================================
    # UI build
    # ===================================================================

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("缠论交易信号监控系统  —  Chan Monitor")
        self.root.geometry("1460x860")
        self.root.configure(bg=BG)

        self._build_style()
        self._build_header()
        self._build_main()
        self._build_status_bar()

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview",
                        background=SURFACE,
                        foreground=TEXT,
                        fieldbackground=SURFACE,
                        rowheight=30,
                        font=FONT,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background="#21262D",
                        foreground=TEXT,
                        font=FONT_BOLD,
                        borderwidth=1,
                        relief="solid")
        style.map("Treeview",
                  background=[("selected", ACCENT_SELECTED)],
                  foreground=[("selected", "#FFFFFF")])
        style.configure("TScrollbar",
                        background=SURFACE,
                        troughcolor=BG,
                        arrowcolor=TEXT_MUTED,
                        borderwidth=0)

    def _build_header(self):
        header = tk.Frame(self.root, bg=HEADER_BG, height=64)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        inner = tk.Frame(header, bg=HEADER_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=20)

        tk.Label(inner, text="缠论交易信号监控系统",
                 font=FONT_H1, fg=TEXT, bg=HEADER_BG).pack(side=tk.LEFT, pady=12)

        codes_str = "  ".join(self.codes)
        tk.Label(inner, text=f"监控标的: {codes_str}",
                 font=FONT_SM, fg=TEXT_MUTED, bg=HEADER_BG).pack(
                     side=tk.LEFT, padx=(30, 0), pady=20)

        self._status_label = tk.Label(inner, text="● 正在加载...",
                                      font=FONT_SM, fg=TEXT_MUTED, bg=HEADER_BG)
        self._status_label.pack(side=tk.RIGHT, pady=20)

    def _build_main(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=(10, 0))

        # ---- LEFT: buy signals ----
        buy_frame = tk.Frame(main, bg=BG)
        buy_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self._build_panel_header(buy_frame, "买入信号", BUY_GREEN,
                                 "≥3 指标  ■ 绿色高亮  |  =2 指标  ■ 灰色  |  跨级别确认  ■ 蓝色")

        self.buy_tree = self._build_tree(buy_frame, "buy")
        self._configure_tags(self.buy_tree, ROW_BUY_STRONG, ROW_BUY_CONFIRM)

        # ---- RIGHT: sell signals ----
        sell_frame = tk.Frame(main, bg=BG)
        sell_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self._build_panel_header(sell_frame, "卖出信号", SELL_RED,
                                 "≥3 指标  ■ 红色高亮  |  =2 指标  ■ 灰色  |  跨级别确认  ■ 橙色")

        self.sell_tree = self._build_tree(sell_frame, "sell")
        self._configure_tags(self.sell_tree, ROW_SELL_STRONG, ROW_SELL_CONFIRM)

    def _build_panel_header(self, parent, title, color, subtitle):
        bar = tk.Frame(parent, bg=SURFACE)
        bar.pack(fill=tk.X)

        dot = tk.Frame(bar, bg=color, width=4, height=24)
        dot.pack(side=tk.LEFT, padx=(12, 8), pady=10)
        dot.pack_propagate(False)

        tk.Label(bar, text=title, font=FONT_H2, fg=color, bg=SURFACE).pack(
            side=tk.LEFT, pady=8)
        tk.Label(bar, text=subtitle, font=FONT_SM, fg=TEXT_MUTED, bg=SURFACE).pack(
            side=tk.RIGHT, padx=12, pady=10)

    def _build_tree(self, parent, _name):
        container = tk.Frame(parent, bg=BG)
        container.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(container, columns=COLUMNS, show="headings")
        for col, w, a in zip(COLUMNS, COL_WIDTHS, COL_ANCHORS):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor=a, minwidth=40)

        scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _configure_tags(self, tree, strong_bg, confirm_bg):
        tree.tag_configure("strong",    background=strong_bg)
        tree.tag_configure("normal",    background=ROW_NORMAL, foreground=TEXT_MUTED)
        tree.tag_configure("confirmed", background=confirm_bg)

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=HEADER_BG, height=30)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self._stats_label = tk.Label(bar, text="",
                                     font=FONT_SM, fg=TEXT_MUTED, bg=HEADER_BG)
        self._stats_label.pack(side=tk.LEFT, padx=16, pady=5)

        tk.Label(bar, text="缠论 Chan Theory  |  MACD / KDJ / BOLL / BIAS",
                 font=FONT_SM, fg=TEXT_MUTED, bg=HEADER_BG).pack(
                     side=tk.RIGHT, padx=16, pady=5)

    # ===================================================================
    # Signal processing  (public signatures preserved for tests)
    # ===================================================================

    def add_buy(self, line, data, is_acc, confirmed=False):
        self.save_csv(data)
        entry = self._make_entry(data, is_acc, confirmed, "buy")
        self._buy_signals.append(entry)
        self._refresh_tree(self.buy_tree, self._buy_signals, "buy")

    def add_sell(self, line, data, is_acc, confirmed=False):
        self.save_csv(data)
        entry = self._make_entry(data, is_acc, confirmed, "sell")
        self._sell_signals.append(entry)
        self._refresh_tree(self.sell_tree, self._sell_signals, "sell")

    def _make_entry(self, data, is_acc, confirmed, direction):
        """Build a sortable signal entry from the raw CSV-row `data`."""
        full_type = data[1]  # e.g. "[日线]一买"
        # extract period & point-type from "[period]type"
        period = full_type.split("]")[0].lstrip("[") if "]" in full_type else ""
        point_type = full_type.split("]")[-1] if "]" in full_type else full_type

        date_str = self._date_key(data[2])
        return {
            "date_sort": pd.Timestamp(date_str),
            "code":     data[0],
            "date":     date_str,
            "period":   period,
            "type":     point_type,
            "full_type": full_type,
            "price":    float(data[3]),
            "indicators": data[4],
            "is_acc":   is_acc,
            "confirmed": confirmed,
            "direction": direction,
        }

    def _refresh_tree(self, tree, signals, direction):
        """Clear and repopulate tree, sorted by date descending."""
        tree.delete(*tree.get_children())

        signals.sort(key=lambda s: s["date_sort"], reverse=True)

        for s in signals:
            if s["is_acc"] and s["confirmed"]:
                tag = "confirmed"
            elif s["is_acc"]:
                tag = "strong"
            else:
                tag = "normal"

            strength_label = self._strength_label(s)
            tree.insert("", tk.END, values=(
                s["code"],
                s["date"],
                s["period"],
                s["type"],
                f"{s['price']:.2f}",
                s["indicators"],
                strength_label,
            ), tags=(tag,))

    @staticmethod
    def _strength_label(s):
        if s["is_acc"] and s["confirmed"]:
            return "强确认"
        if s["is_acc"]:
            return "精准"
        if s["confirmed"]:
            return "强参考"
        return "参考"

    # ===================================================================
    # Render
    # ===================================================================

    def render(self, code, all_res):
        now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")

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

        self._update_stats()

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

    # ===================================================================
    # Status / stats
    # ===================================================================

    def _update_stats(self):
        if not hasattr(self, "_threads_done"):
            return
        self._threads_done += 1
        if self._total_threads == 0:
            return
        buy_count = len(self._buy_signals)
        sell_count = len(self._sell_signals)
        acc_buy = sum(1 for s in self._buy_signals if s["is_acc"])
        acc_sell = sum(1 for s in self._sell_signals if s["is_acc"])
        conf_buy = sum(1 for s in self._buy_signals if s["confirmed"])
        conf_sell = sum(1 for s in self._sell_signals if s["confirmed"])

        status_text = "● 在线"
        if self._threads_done >= self._total_threads:
            status_text += "  |  数据已就绪"

        self.root.after(0, self._set_status, status_text)
        self.root.after(0, self._set_stats,
                        f"买入: {buy_count} 个 (精准 {acc_buy}, 跨级别确认 {conf_buy})  |  "
                        f"卖出: {sell_count} 个 (精准 {acc_sell}, 跨级别确认 {conf_sell})")

    def _set_status(self, text):
        self._status_label.config(text=text)

    def _set_stats(self, text):
        self._stats_label.config(text=text)

    # ===================================================================
    # Threading
    # ===================================================================

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
