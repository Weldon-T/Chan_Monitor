import sys
from ui.monitor_window import MonitorWindow

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python main.py 股票代码 [股票代码 ...]")
        print("示例: python main.py 000001.SZ 600519.SH")
        sys.exit(1)

    gui = MonitorWindow(sys.argv[1:])
    gui.start()