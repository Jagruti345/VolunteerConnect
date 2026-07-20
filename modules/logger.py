"""
Simple file + console logger. Every step of provisioning is recorded here
so you have an audit trail of exactly what automation did.
"""

import datetime
import os
from config import LOG_DIR, LOG_FILE


def _write(level, message):
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [{level}] {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


def write_log(message):
    _write("INFO", message)


def write_success(message):
    _write("OK", f"[OK] {message}")


def write_error(message):
    _write("ERROR", f"[FAIL] {message}")


def write_warn(message):
    _write("WARN", message)
