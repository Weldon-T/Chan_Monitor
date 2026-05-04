# ======================
# Tushare 免费账号配置
# ======================
import os
from dotenv import load_dotenv
load_dotenv()
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 日线拉取最近 2 年
HISTORY_DAYS = 400

# 分析级别（日线/周线/月线，全部免费可用）
LEVELS = ["日线", "周线", "月线"]

# 刷新间隔（秒）
REFRESH_INTERVAL = 3600