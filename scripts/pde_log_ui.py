#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"
RUNNER = REPO_ROOT / "live" / "run_polymarket_pde.py"

INSTANCE_PATTERNS = {
    "all": [],
    "live": ["POLYMARKET-001"],
    "sandbox": ["POLYMARKET-SBX"],
}

PRESET_PATTERNS = {
    "all": [],
    "fills": ["OrderFilled", "PositionOpened", "position_closed", "PHASE_B_SETTLE"],
    "orders": [
        "OrderInitialized",
        "order_submitted",
        "OrderAccepted",
        "OrderDenied",
        "Cannot submit market order",
    ],
    "pnl": ["[PNL]", "PHASE_B_SETTLE", "Round PnL", "Total:"],
    "errors": ["[ERROR]", "[WARN]", "OrderDenied", "Cannot submit market order", "Traceback"],
}


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def recent_logs(limit: int = 15) -> list[Path]:
    if not LOG_DIR.exists():
        return []
    return sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def build_log_file(mode: str) -> Path:
    ensure_log_dir()
    return LOG_DIR / f"pde_{mode}_{now_str()}.log"


def start_with_log(mode: str) -> None:
    if not RUNNER.exists():
        print(f"[ERROR] Runner not found: {RUNNER}")
        return

    logfile = build_log_file(mode)
    cmd = [sys.executable, str(RUNNER), "--mode", mode]

    print("\n=== Start Strategy ===")
    print(f"Mode: {mode}")
    print(f"Log : {logfile}")
    print("Press Ctrl+C to stop.\n")

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        with logfile.open("a", encoding="utf-8", errors="replace") as f:
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
                f.write(line)
                f.flush()
    except KeyboardInterrupt:
        print("\n[WARN] Stopping process...")
        proc.terminate()
    finally:
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print(f"\n[OK] Process exited with code {proc.returncode}")
        print(f"[OK] Log saved: {logfile}")


def line_match(line: str, instance: str, preset: str, extra_keywords: list[str]) -> bool:
    for k in INSTANCE_PATTERNS[instance]:
        if k not in line:
            return False

    for k in PRESET_PATTERNS[preset]:
        if k not in line:
            return False

    for k in extra_keywords:
        if k and k not in line:
            return False

    return True


def choose_mode() -> str:
    mapping = {"1": "sandbox", "2": "live", "3": "both"}
    while True:
        print("\nChoose mode:")
        print("  1) sandbox")
        print("  2) live")
        print("  3) both (recommended)")
        c = input("Select [1-3] (default 3): ").strip() or "3"
        if c in mapping:
            return mapping[c]
        print("Invalid input.")


def choose_instance() -> str:
    mapping = {"1": "all", "2": "live", "3": "sandbox"}
    while True:
        print("\nInstance filter:")
        print("  1) all")
        print("  2) live only (POLYMARKET-001)")
        print("  3) sandbox only (POLYMARKET-SBX)")
        c = input("Select [1-3] (default 2): ").strip() or "2"
        if c in mapping:
            return mapping[c]
        print("Invalid input.")


def choose_preset() -> str:
    mapping = {"1": "all", "2": "fills", "3": "orders", "4": "pnl", "5": "errors"}
    while True:
        print("\nContent preset:")
        print("  1) all")
        print("  2) fills")
        print("  3) orders")
        print("  4) pnl")
        print("  5) errors")
        c = input("Select [1-5] (default 2): ").strip() or "2"
        if c in mapping:
            return mapping[c]
        print("Invalid input.")


def choose_log_file() -> Path | None:
    logs = recent_logs()
    if not logs:
        print("[WARN] No log files found in ./logs")
        return None

    print("\nRecent logs:")
    for i, p in enumerate(logs, start=1):
        print(f"  {i:>2}) {p.name}")

    print("  L) latest")
    c = input("Select file index or L (default L): ").strip().lower() or "l"

    if c == "l":
        return logs[0]

    if c.isdigit():
        idx = int(c)
        if 1 <= idx <= len(logs):
            return logs[idx - 1]

    print("Invalid selection.")
    return None


def parse_extra_keywords(raw: str) -> list[str]:
    if not raw.strip():
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def stream_lines(file_path: Path, follow: bool) -> Iterable[str]:
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        if not follow:
            yield from f
            return

        for line in f:
            yield line

        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(0.3)


def view_log(follow: bool) -> None:
    file_path = choose_log_file()
    if file_path is None:
        return

    instance = choose_instance()
    preset = choose_preset()
    raw_extra = input("Extra keywords (comma-separated, optional): ").strip()
    extras = parse_extra_keywords(raw_extra)

    print("\n=== View Log ===")
    print(f"File    : {file_path}")
    print(f"Instance: {instance}")
    print(f"Preset  : {preset}")
    print(f"Extra   : {extras if extras else 'none'}")
    if follow:
        print("Mode    : follow (Ctrl+C to stop)")
    print("----------------------------------------")

    try:
        for line in stream_lines(file_path, follow=follow):
            if line_match(line, instance, preset, extras):
                print(line, end="")
    except KeyboardInterrupt:
        print("\n[OK] Stop viewing.")


def print_menu() -> None:
    print("\n" + "=" * 46)
    print(" PDE Log UI (friendly console tool)")
    print("=" * 46)
    print("1) Start strategy (auto write log file)")
    print("2) View log (filtered, one-shot)")
    print("3) Tail log (filtered, realtime)")
    print("4) Show recent log files")
    print("5) Exit")


def show_recent_logs() -> None:
    logs = recent_logs(limit=20)
    if not logs:
        print("[WARN] No log files found in ./logs")
        return
    print("\nRecent log files:")
    for p in logs:
        t = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"- {p.name}  ({t})")


def main() -> None:
    ensure_log_dir()

    while True:
        print_menu()
        choice = input("Choose [1-5]: ").strip()

        if choice == "1":
            mode = choose_mode()
            start_with_log(mode)
        elif choice == "2":
            view_log(follow=False)
        elif choice == "3":
            view_log(follow=True)
        elif choice == "4":
            show_recent_logs()
        elif choice == "5":
            print("Bye.")
            return
        else:
            print("Invalid input.")


if __name__ == "__main__":
    main()
