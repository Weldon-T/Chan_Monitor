import numpy as np
import pandas as pd

class ChanLunEngine:
    def analyze(self, df, period_name, code):
        df = df.copy().reset_index(drop=True)
        total_k = len(df)
        print(f"[统计] [{code}] [{period_name}] K线总数：{total_k}")

        if total_k < 30:
            print(f"[WARN] [{code}] [{period_name}] 数据不足\n")
            return {"accurate_buy": [], "accurate_sell": [], "normal_buy": [], "normal_sell": []}

        df = self.add_indicators(df)
        dates = df["date"].values
        closes = df["close"].values
        high = df["high"].tolist()
        low = df["low"].tolist()

        # ====================== 日线专用 宽松实战逻辑（默认启用） ======================
        fx_list = self.get_fx_daily(high, low)
        bi_list = self.get_bi_daily(fx_list, high, low)
        xd_list = self.get_xd_daily(bi_list)
        zs_list = self.get_zhongshu_daily(xd_list)

        # ====================== 原严格缠论（已注释，保留不删除，1分钟用） ======================
        # processed_high, processed_low = self.handle_include(high, low)
        # fx_list = self.get_fx(processed_high, processed_low)
        # bi_list = self.get_bi(fx_list, processed_high, processed_low)
        # xd_list = self.get_xd(bi_list)
        # zs_list = self.get_zhongshu(xd_list)

        print(f"[OK] [{code}] [{period_name}] 分型：{len(fx_list)} | 笔：{len(bi_list)} | 线段：{len(xd_list)} | 中枢：{len(zs_list)}")

        buy_points, sell_points = self.get_standard_chan_signals_daily(xd_list, zs_list, dates, closes)

        accurate_buy, accurate_sell, normal_buy, normal_sell = [], [], [], []

        for idx, dt, p, tp in buy_points:
            ok, names, cnt = self.check_buy(df, idx)
            print(f"[信号] [{code}] [{period_name}] {tp} | {dt} | 价:{p:.2f} | 指标:{cnt}/4 [{names}]")
            item = {"time": dt, "price": p, "type": f"[{period_name}]{tp}", "indicators": names}
            if cnt >= 3:
                accurate_buy.append(item)
            elif cnt == 2:
                normal_buy.append(item)

        for idx, dt, p, tp in sell_points:
            ok, names, cnt = self.check_sell(df, idx)
            print(f"[信号] [{code}] [{period_name}] {tp} | {dt} | 价:{p:.2f} | 指标:{cnt}/4 [{names}]")
            item = {"time": dt, "price": p, "type": f"[{period_name}]{tp}", "indicators": names}
            if cnt >= 3:
                accurate_sell.append(item)
            elif cnt == 2:
                normal_sell.append(item)

        print(f"[结果] [{code}] [{period_name}] 精准(>=3)买:{len(accurate_buy)} 卖:{len(accurate_sell)} | 参考(=2)买:{len(normal_buy)} 卖:{len(normal_sell)}\n")
        return {
            "accurate_buy": accurate_buy, "accurate_sell": accurate_sell,
            "normal_buy": normal_buy, "normal_sell": normal_sell
        }

    # -------------------------------------------------------------------------
    # 【日线专用】分型
    # -------------------------------------------------------------------------
    def get_fx_daily(self, high, low):
        r = []
        for i in range(1, len(high)-1):
            if high[i-1] < high[i] > high[i+1]:
                r.append((i, "顶"))
            if low[i-1] > low[i] < low[i+1]:
                r.append((i, "底"))
        return r

    # -------------------------------------------------------------------------
    # 【日线专用】笔
    # -------------------------------------------------------------------------
    def get_bi_daily(self, fx, high, low):
        r = []
        if len(fx) < 2:
            return r
        last_type = None
        last_idx = None
        last_high = None
        last_low = None
        for idx, tp in fx:
            if last_type is None:
                last_type = tp
                last_idx = idx
                last_high = high[idx]
                last_low = low[idx]
                continue
            if tp == last_type:
                continue
            if last_type == "底" and tp == "顶":
                if idx > last_idx + 1:
                    r.append({
                        "s": last_idx, "e": idx, "dir": "up",
                        "high": high[idx], "low": low[last_idx]
                    })
            elif last_type == "顶" and tp == "底":
                if idx > last_idx + 1:
                    r.append({
                        "s": last_idx, "e": idx, "dir": "down",
                        "high": high[last_idx], "low": low[idx]
                    })
            last_type = tp
            last_idx = idx
            last_high = high[idx]
            last_low = low[idx]
        return r

    # -------------------------------------------------------------------------
    # 【日线专用】线段
    # -------------------------------------------------------------------------
    def get_xd_daily(self, bi_list):
        xd = []
        if len(bi_list) < 3:
            return xd
        current_start = bi_list[0]["s"]
        current_dir = bi_list[0]["dir"]
        current_high = bi_list[0]["high"]
        current_low = bi_list[0]["low"]
        for i in range(1, len(bi_list)):
            bi = bi_list[i]
            if bi["dir"] == current_dir:
                current_high = max(current_high, bi["high"])
                current_low = min(current_low, bi["low"])
            else:
                if i >= 2:
                    xd.append({
                        "s": current_start, "e": bi_list[i-1]["e"], "dir": current_dir,
                        "high": current_high, "low": current_low
                    })
                current_dir = bi["dir"]
                current_start = bi["s"]
                current_high = bi["high"]
                current_low = bi["low"]
        if len(xd) == 0 or xd[-1]["e"] != bi_list[-1]["e"]:
            xd.append({
                "s": current_start, "e": bi_list[-1]["e"], "dir": current_dir,
                "high": current_high, "low": current_low
            })
        return xd

    # -------------------------------------------------------------------------
    # 【日线专用】中枢（3线段重叠即成立）
    # -------------------------------------------------------------------------
    def get_zhongshu_daily(self, xd_list):
        zs = []
        if len(xd_list) < 3:
            return zs
        for i in range(len(xd_list) - 2):
            a = xd_list[i]
            b = xd_list[i+1]
            c = xd_list[i+2]
            zd = max(a["low"], b["low"], c["low"])
            zg = min(a["high"], b["high"], c["high"])
            if zg > zd + 0.01:
                zs.append({
                    "zg": zg, "zd": zd, "mid": (zg + zd) / 2,
                    "end_idx": i + 2, "segments": [a, b, c]
                })
        return zs

    # -------------------------------------------------------------------------
    # 【日线专用】买卖点
    # -------------------------------------------------------------------------
    def get_standard_chan_signals_daily(self, xd_list, zs_list, dates, closes):
        buy = []
        sell = []
        if not zs_list or not xd_list:
            return buy, sell
        zs = zs_list[-1]
        used = set()
        for i, xd in enumerate(xd_list):
            idx = xd["e"]
            if idx >= len(dates) or idx in used:
                continue
            dt = dates[idx]
            p = round(closes[idx], 2)

            # 买点
            if xd["dir"] == "down":
                if xd["low"] < zs["zd"]:
                    buy.append((idx, dt, p, "一买"))
                    used.add(idx)
                elif zs["zd"] <= xd["low"] < zs["mid"]:
                    buy.append((idx, dt, p, "二买"))
                    used.add(idx)
            if xd["dir"] == "up" and xd["low"] > zs["zg"]:
                buy.append((idx, dt, p, "三买"))
                used.add(idx)

            # 卖点
            if xd["dir"] == "up":
                if xd["high"] > zs["zg"]:
                    sell.append((idx, dt, p, "一卖"))
                    used.add(idx)
                elif zs["mid"] < xd["high"] <= zs["zg"]:
                    sell.append((idx, dt, p, "二卖"))
                    used.add(idx)
            if xd["dir"] == "down" and xd["high"] < zs["zd"]:
                sell.append((idx, dt, p, "三卖"))
                used.add(idx)
        return buy, sell

    # -------------------------------------------------------------------------
    # 以下为原严格版代码（完整保留，已注释，不删除）
    # -------------------------------------------------------------------------
    # def handle_include(self, high, low):
    #     if len(high) < 2:
    #         return high, low
    #     processed = [(high[0], low[0])]
    #     for i in range(1, len(high)):
    #         last_h, last_l = processed[-1]
    #         curr_h, curr_l = high[i], low[i]
    #         if (last_h >= curr_h and last_l <= curr_l) or (curr_h >= last_h and curr_l <= last_l):
    #             if last_h > curr_h:
    #                 new_h = last_h
    #                 new_l = max(last_l, curr_l)
    #             else:
    #                 new_h = min(last_h, curr_h)
    #                 new_l = last_l
    #             processed[-1] = (new_h, new_l)
    #         else:
    #             processed.append((curr_h, curr_l))
    #     return [x[0] for x in processed], [x[1] for x in processed]

    # def get_fx(self, high, low):
    #     r = []
    #     min_amplitude = 0.001
    #     for i in range(1, len(high)-1):
    #         if high[i-1] < high[i] and high[i] > high[i+1] and low[i] >= low[i-1] and low[i] >= low[i+1]:
    #             if high[i] - min(low[i-1], low[i+1]) > min_amplitude:
    #                 r.append((i, "顶"))
    #         if low[i-1] > low[i] and low[i] < low[i+1] and high[i] <= high[i-1] and high[i] <= high[i+1]:
    #             if max(high[i-1], high[i+1]) - low[i] > min_amplitude:
    #                 r.append((i, "底"))
    #     filtered = []
    #     lt, lv, li = None, -1, -1
    #     for idx, tp in r:
    #         if tp != lt:
    #             if lt is not None:
    #                 filtered.append((li, lt))
    #             lt, lv, li = tp, (high[idx] if tp == "顶" else low[idx]), idx
    #         else:
    #             if tp == "顶" and high[idx] > lv:
    #                 lv, li = high[idx], idx
    #             elif tp == "底" and low[idx] < lv:
    #                 lv, li = low[idx], idx
    #     if lt is not None:
    #         filtered.append((li, lt))
    #     return filtered

    # def get_bi(self, fx, high, low):
    #     r = []
    #     if len(fx) < 2:
    #         return r
    #     pairs = []
    #     i = 0
    #     while i < len(fx)-1:
    #         i1, t1 = fx[i]
    #         i2, t2 = fx[i+1]
    #         if (t1 == "底" and t2 == "顶") or (t1 == "顶" and t2 == "底"):
    #             if abs(i2 - i1) >= 2 and (i2 - i1 + 1) >= 5:
    #                 pairs.append((i1, t1, i2, t2))
    #                 i += 2
    #             else:
    #                 i += 1
    #         else:
    #             i += 1
    #     for i1, t1, i2, t2 in pairs:
    #         if t1 == "底" and t2 == "顶" and high[i2] > high[i1]:
    #             r.append({"s": i1, "e": i2, "dir": "up", "high": high[i2], "low": low[i1], "amplitude": high[i2]-low[i1]})
    #         elif t1 == "顶" and t2 == "底" and low[i2] < low[i1]:
    #             r.append({"s": i1, "e": i2, "dir": "down", "high": high[i1], "low": low[i2], "amplitude": high[i1]-low[i2]})
    #     return r

    # def get_xd(self, bi_list):
    #     if len(bi_list) < 3:
    #         return []
    #     feat = []
    #     for b in bi_list:
    #         if b["dir"] == "up":
    #             feat.append((b["low"], b["high"], b["s"], b["e"], "down"))
    #         else:
    #             feat.append((b["high"], b["low"], b["s"], b["e"], "up"))
    #     xd = []
    #     s = 0
    #     cd = bi_list[0]["dir"]
    #     for i in range(2, len(feat)):
    #         f1, f2, f3 = feat[i-2], feat[i-1], feat[i]
    #         if cd == "down" and f2[0]>f1[0] and f2[0]>f3[0] and f2[1]>f1[1] and f2[1]>f3[1]:
    #             seg = bi_list[s:i]
    #             xd.append({"s": seg[0]["s"], "e": seg[-1]["e"], "dir": cd,
    #                       "high": max(b["high"] for b in seg), "low": min(b["low"] for b in seg)})
    #             s = i
    #             cd = "up"
    #         elif cd == "up" and f2[1]<f1[1] and f2[1]<f3[1] and f2[0]<f1[0] and f2[0]<f3[0]:
    #             seg = bi_list[s:i]
    #             xd.append({"s": seg[0]["s"], "e": seg[-1]["e"], "dir": cd,
    #                       "high": max(b["high"] for b in seg), "low": min(b["low"] for b in seg)})
    #             s = i
    #             cd = "down"
    #     if s < len(bi_list):
    #         seg = bi_list[s:]
    #         if len(seg)>=3:
    #             xd.append({"s": seg[0]["s"], "e": seg[-1]["e"], "dir": cd,
    #                       "high": max(b["high"] for b in seg), "low": min(b["low"] for b in seg)})
    #     return xd

    # def get_zhongshu(self, xd_list):
    #     zs = []
    #     if len(xd_list) <3:
    #         return zs
    #     for i in range(len(xd_list)-2):
    #         x1,x2,x3 = xd_list[i],xd_list[i+1],xd_list[i+2]
    #         if not ((x1["dir"]=="up"and x2["dir"]=="down"and x3["dir"]=="up")or(x1["dir"]=="down"and x2["dir"]=="up"and x3["dir"]=="down")):
    #             continue
    #         zg = min(x1["high"],x2["high"],x3["high"])
    #         zd = max(x1["low"],x2["low"],x3["low"])
    #         if zg>zd:
    #             zs.append({"idx":i,"zg":zg,"zd":zd,"mid":(zg+zd)/2,"end_idx":i+2,"segments":[x1,x2,x3]})
    #     return zs

    # def check_bc(self, df, idx, direction):
    #     if idx<20:
    #         return False
    #     p = df["close"].iloc[max(0,idx-20):idx+1].values
    #     m = (df["dif"]-df["dea"]).iloc[max(0,idx-20):idx+1].values
    #     if direction=="down":
    #         return p[-1]==p.min() and m[-1]>m.min()
    #     elif direction=="up":
    #         return p[-1]==p.max() and m[-1]<m.max()
    #     return False

    # def get_standard_chan_signals(self, xd_list, zs_list, high, low, dates, closes, df):
    #     buy,sell = [],[]
    #     if not xd_list or not zs_list:
    #         return buy,sell
    #     for zs in sorted(zs_list,key=lambda x:x["end_idx"],reverse=True):
    #         af = [(i,x) for i,x in enumerate(xd_list) if i>zs["end_idx"]]
    #         ub,us = set(),set()
    #         dn = [x for x in af if x[1]["dir"]=="down"]
    #         for seq,(i,xd) in enumerate(dn):
    #             idx = xd["e"]
    #             if idx>=len(dates) or idx in ub:continue
    #             dt,pr = dates[idx],round(closes[idx],2)
    #             if seq==0 and self.check_bc(df,idx,"down"):
    #                 buy.append((idx,dt,pr,"一买"));ub.add(idx);fbp=pr
    #             elif seq==1 and "fbp" in locals() and xd["low"]>fbp*0.995:
    #                 buy.append((idx,dt,pr,"二买"));ub.add(idx)
    #             elif seq==2 and xd["low"]>zs["zg"]:
    #                 buy.append((idx,dt,pr,"三买"));ub.add(idx)
    #         up = [x for x in af if x[1]["dir"]=="up"]
    #         for seq,(i,xd) in enumerate(up):
    #             idx = xd["e"]
    #             if idx>=len(dates) or idx in us:continue
    #             dt,pr = dates[idx],round(closes[idx],2)
    #             if seq==0 and self.check_bc(df,idx,"up"):
    #                 sell.append((idx,dt,pr,"一卖"));us.add(idx);fsp=pr
    #             elif seq==1 and "fsp" in locals() and xd["high"]<fsp*1.005:
    #                 sell.append((idx,dt,pr,"二卖"));us.add(idx)
    #             elif seq==2 and xd["high"]<zs["zd"]:
    #                 sell.append((idx,dt,pr,"三卖"));us.add(idx)
    #         break
    #     return buy,sell

    # ====================== 原指标逻辑（完全不变） ======================
    def check_buy(self, df, i):
        try:
            macd = df["dif"].iat[i] > df["dea"].iat[i]
            kdj  = df["k"].iat[i] > df["d"].iat[i] and df["j"].iat[i] < 30
            boll = df["close"].iat[i] <= df["bold"].iat[i] * 1.03
            bias = df["bias"].iat[i] < -2.5
            arr = [x for x, o in zip(["MACD","KDJ","BOLL","BIAS"], [macd,kdj,boll,bias]) if o]
            return len(arr)>=2, ",".join(arr), len(arr)
        except:
            return False, "", 0

    def check_sell(self, df, i):
        try:
            macd = df["dif"].iat[i] < df["dea"].iat[i]
            kdj  = df["k"].iat[i] < df["d"].iat[i] and df["j"].iat[i] > 70
            boll = df["close"].iat[i] >= df["bolu"].iat[i] * 0.97
            bias = df["bias"].iat[i] > 2.5
            arr = [x for x, o in zip(["MACD","KDJ","BOLL","BIAS"], [macd,kdj,boll,bias]) if o]
            return len(arr)>=2, ",".join(arr), len(arr)
        except:
            return False, "", 0

    def add_indicators(self, df):
        c = df["close"].values
        h = df["high"].values
        l = df["low"].values
        n = len(c)

        ema12 = np.convolve(c, np.ones(12)/12, "same")
        ema26 = np.convolve(c, np.ones(26)/26, "same")
        df["dif"] = ema12 - ema26
        df["dea"] = np.convolve(df["dif"], np.ones(9)/9, "same")

        k,d,j = np.zeros(n),np.zeros(n),np.zeros(n)
        k[0]=d[0]=50
        for i in range(1,n):
            ph = h[max(0,i-9):i+1].max()
            pl = l[max(0,i-9):i+1].min()
            rsv = (c[i]-pl)/(ph-pl+1e-5)*100
            k[i] = (2*k[i-1]+rsv)/3
            d[i] = (2*d[i-1]+k[i])/3
        df["k"]=k; df["d"]=d; df["j"]=3*k-2*d

        ma20 = np.convolve(c, np.ones(20)/20, "same")
        std = np.array([np.std(c[max(0,i-19):i+1]) for i in range(n)])
        df["bolu"]=ma20+2*std; df["bold"]=ma20-2*std

        ma6 = np.convolve(c, np.ones(6)/6, "same")
        df["bias"] = (c-ma6)/(ma6+1e-5)*100
        return df