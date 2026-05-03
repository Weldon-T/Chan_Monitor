from ui.monitor_window import MonitorWindow

if __name__ == "__main__":
    watch_list = [
        "603043.SH",
        "600104.SH",
        "000035.SZ",
    ]

    gui = MonitorWindow(watch_list)
    gui.start()