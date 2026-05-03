# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A股缠论交易信号监控工具。通过 Tushare 获取日线数据，合成周线/月线，按缠论体系识别顶底分型→笔→线段→中枢→买卖点，再用 MACD/KDJ/BOLL/BIAS 四个指标交叉确认信号强度，最终在 Tkinter GUI 中展示并写入 CSV。

## 环境

项目使用 `.venv` 虚拟环境，所有 pip 安装/卸载操作必须先激活：

```bash
# Windows (Git Bash)
source .venv/Scripts/activate
pip install <pkg>

# 或者直接使用 venv 内的解释器，不激活
.venv/Scripts/python.exe -m pip install <pkg>
```

## 运行

```bash
python main.py
```

