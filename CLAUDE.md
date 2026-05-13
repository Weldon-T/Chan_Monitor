# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A股缠论交易信号监控工具。通过 Tushare 获取日线数据，合成周线/月线，按缠论体系识别顶底分型→笔→线段→中枢→买卖点，再用 MACD/KDJ/BOLL/BIAS 四个指标交叉确认信号强度，最终在 Tkinter GUI 中展示并写入 CSV。


## Git / GitHub

- 仓库地址：`https://github.com/Weldon-T/Chan_Monitor`


## 运行

```bash
python main.py
```

