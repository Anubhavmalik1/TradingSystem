#!/usr/bin/env python3
"""
run_all.py - Production-ready launcher for trading components

This script launches:
1. Feed Distributor
2. OMS (mock/init)
3. RMS (mock/init)
4. Strategy Engine(s)

Currently enabled:
- Short Straddle Strategy (9:20 AM seller)

Disabled:
- Mean Reversion Strategy (commented)
"""

import subprocess
import time
import sys
from datetime import datetime

# -----------------------------
# IMPORT TELEGRAM ALERT
# -----------------------------
from src.telegram_alert import send_telegram

# -----------------------------
# CONFIGURATION
# -----------------------------
COMPONENTS = [
    {"script": "src/simulator_feed_distributor.py", "name": "Feed Distributor", "wait": 3},
    {"script": None, "name": "OMS", "wait": 1},   # OMS module initialization
    {"script": None, "name": "RMS", "wait": 1},   # RMS module initialization

    # -------------------------------
    # STRATEGY EXECUTION CONTROL
    # -------------------------------

    # ENABLE THIS to run 9:20 Short Straddle Strategy
    # {"script": "src/strategy_straddle_seller.py", "name": "Short Straddle Strategy", "wait": 0},

    # ENABLED: Mean Reversion Strategy
    {"script": "src/strategy_mean_reversion.py", "name": "Mean Reversion Strategy", "wait": 0},
]


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def timestamp():
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def launch_script(script_name, display_name):
    """
    Launch a Python script as a subprocess with console messages.

    Args:
        script_name (str): Python script file to execute.
        display_name (str): Display name for console messages.
    
    Returns:
        subprocess.Popen or None
    """
    print(f"[{timestamp()}] {display_name}: Initiating...")
    time.sleep(1)
    print(f"[{timestamp()}] {display_name}: Launching...")

    if script_name:
        proc = subprocess.Popen([sys.executable, script_name])
        print(f"[{timestamp()}] {display_name}: Launched (PID: {proc.pid})\n")

        # Telegram confirmation
        send_telegram(f"Launched {display_name} (PID: {proc.pid})")

        return proc
    else:
        print(f"[{timestamp()}] {display_name}: Launched\n")
        send_telegram(f"Launched {display_name}")
        return None


# -----------------------------
# MAIN LAUNCHER
# -----------------------------
def main():
    """Launch all trading components in sequence."""
    processes = []

    print("="*60)
    print(f"[{timestamp()}] Starting Trading System Launcher")
    print("="*60, "\n")

    # Telegram start notification
    send_telegram("Trading System Launcher Started")

    try:
        for comp in COMPONENTS:
            proc = launch_script(comp["script"], comp["name"])
            if proc:
                processes.append(proc)
            time.sleep(comp.get("wait", 1))

        print(f"[{timestamp()}] All components launched successfully.\n")
        print("Monitoring processes... Press Ctrl+C to terminate.\n")

        send_telegram("All components launched successfully. Monitoring...")

        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] Termination requested by user. Shutting down components...")
        send_telegram("User requested shutdown. Terminating processes...")

        for p in processes:
            p.terminate()
        time.sleep(2)
        print(f"[{timestamp()}] All components terminated gracefully.")
        send_telegram("All components terminated.")

    print(f"[{timestamp()}] Launcher exited.")

# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()
