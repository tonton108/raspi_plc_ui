# logger.py

import time
import csv
import os
import datetime
import json
from utils.comm import read_d100

SETTING_PATH = os.path.join("config", "setting.json")
LOG_PATH = os.path.join("logs", "log.csv")

def load_settings():
    with open(SETTING_PATH, "r") as f:
        return json.load(f)

def append_log(timestamp, value):
    os.makedirs("logs", exist_ok=True)
    is_new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "value"])
        writer.writerow([timestamp, value])

def start_logging():
    settings = load_settings()
    ip = settings["ip"]
    port = int(settings["port"])
    manufacturer = settings["manufacturer"]
    interval = int(settings["interval"])

    print(f"[ロギング開始] {manufacturer} @ {ip}:{port} / {interval}sごと")

    while True:
        value = read_d100(ip, port, manufacturer)
        now = datetime.datetime.now().isoformat()
        append_log(now, value)
        print(f"[{now}] D100 = {value}")
        time.sleep(interval)

if __name__ == "__main__":
    start_logging()
