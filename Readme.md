依赖见 `requirements.txt`：tushare, pandas, tqdm, timeout_decorator。

## 架构

```
main.py                  # 入口，配置监控股票列表，启动 MonitorWindow
config/settings.py       # Tushare token，历史天数，分析级别，刷新间隔
core/data_api.py         # DataAPI：调用 tushare pro_api 拉日线，支持周/月线 resample
core/chan_engine.py      # ChanLunEngine：缠论核心，分型→笔→线段→中枢→买卖点，指标确认
ui/monitor_window.py     # MonitorWindow：Tkinter GUI，多线程拉数据，展示信号并写 CSV
```

## 关键逻辑

### 缠论分析链路（日线宽松版，默认启用）
`get_fx_daily` → `get_bi_daily` → `get_xd_daily` → `get_zhongshu_daily` → `get_standard_chan_signals_daily`

- **中枢**由连续3条线段的高/低点重叠区域确定（ZG = min highs, ZD = max lows），ZG > ZD 即成立
- **买点**：向下线段低点 < ZD → 一买；在 [ZD, mid) → 二买；向上线段低点 > ZG → 三买
- **卖点**：向上线段高点 > ZG → 一卖；在 (mid, ZG] → 二卖；向下线段高点 < ZD → 三卖

### 信号分级
- `check_buy` / `check_sell` 用 4 个指标（MACD 金叉/死叉、KDJ 超卖/超买、布林下轨/上轨、BIAS 乖离率）确认
- ≥3 个通过 → 精准信号（`accurate_buy/sell`），GUI 绿色/红色高亮
- =2 个通过 → 参考信号（`normal_buy/sell`），白色显示

### 严格版缠论
`chan_engine.py` 尾部有完整注释掉的严格版代码（包含处理、分型过滤、笔的K线数量约束、线段特征序列、背驰检测），标注为"1分钟用"，当前日线不用。

## CSV 输出

`trading_signals.csv`，列：股票代码, 级别类型, 日期, 价格, 确认指标, 记录时间。仅记录 GUI 中显示的条目。
