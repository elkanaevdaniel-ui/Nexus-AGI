#!/usr/bin/env python3
"""
NEXUS AGI Watchdog — monitors and auto-restarts all services.
Checks every 30 seconds. Logs to logs/watchdog.log.
"""
import subprocess
import time
import os
import sys
import socket
import logging
from pathlib import Path

BOT_DIR = Path(__file__).parent
LOG_DIR = BOT_DIR / "logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Watchdog] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_DIR / "watchdog.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Service definitions ───────────────────────────────────────────────────────
SERVICES = [
    {
        "name": "HERALD Bot",
        "pid_file": "/tmp/linkedin_bot.pid",
        "process_pattern": "run.py",
        "start_cmd": [sys.executable, "run.py"],
        "cwd": str(BOT_DIR),
        "log": str(LOG_DIR / "bot.log"),
        "critical": True,
    },
    {
        "name": "LinkedIn Dashboard",
        "pid_file": "/tmp/linkedin_dashboard.pid",
        "process_pattern": "dashboard/app.py",
        "port": 7860,
        "start_cmd": [sys.executable, "dashboard/app.py"],
        "cwd": str(BOT_DIR),
        "log": str(LOG_DIR / "dashboard.log"),
        "critical": False,
    },
    {
        "name": "JARVIS PWA",
        "pid_file": "/tmp/jarvis_pwa.pid",
        "process_pattern": "jarvis_pwa_server.py",
        "port": 7861,
        "start_cmd": [sys.executable, str(BOT_DIR.parent / "nexus-agi" / "interfaces" / "jarvis-pwa" / "jarvis_pwa_server.py")],
        "cwd": str(BOT_DIR),
        "log": str(LOG_DIR / "jarvis_pwa.log"),
        "critical": False,
    },
    {
        "name": "NEXUS Dashboard",
        "pid_file": "/tmp/nexus_dashboard.pid",
        "process_pattern": "nexus_dashboard_server.py",
        "port": 7862,
        "start_cmd": [sys.executable, str(BOT_DIR.parent / "nexus-agi" / "interfaces" / "dashboard" / "nexus_dashboard_server.py")],
        "cwd": str(BOT_DIR),
        "log": str(LOG_DIR / "nexus_dashboard.log"),
        "critical": False,
    },
    {
        "name": "JARVIS Phone",
        "pid_file": "/tmp/jarvis_phone.pid",
        "process_pattern": "jarvis_phone_server.py",
        "port": 7863,
        "start_cmd": [sys.executable, str(BOT_DIR.parent / "nexus-agi" / "interfaces" / "jarvis-phone" / "jarvis_phone_server.py")],
        "cwd": str(BOT_DIR),
        "log": str(LOG_DIR / "jarvis_phone.log"),
        "critical": False,
    },
]


def is_pid_alive(pid_file: str) -> bool:
    """Check if process with PID from file is running."""
    try:
        pid = int(Path(pid_file).read_text().strip())
        os.kill(pid, 0)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False


def is_port_open(port: int) -> bool:
    """Check if a port is accepting connections."""
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def is_service_healthy(svc: dict) -> bool:
    """Check if a service is running via PID and optionally port."""
    if not is_pid_alive(svc["pid_file"]):
        return False
    if "port" in svc and not is_port_open(svc["port"]):
        return False
    return True


def restart_service(svc: dict) -> bool:
    """Restart a single service."""
    log.warning("Restarting %s...", svc["name"])
    try:
        log_fh = open(svc["log"], "a")
        proc = subprocess.Popen(
            svc["start_cmd"],
            cwd=svc["cwd"],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
        Path(svc["pid_file"]).write_text(str(proc.pid))
        log.info("%s restarted → PID %d", svc["name"], proc.pid)
        return True
    except Exception as exc:
        log.error("Failed to restart %s: %s", svc["name"], exc)
        return False


if __name__ == "__main__":
    log.info("NEXUS Watchdog starting — monitoring %d services", len(SERVICES))

    while True:
        for svc in SERVICES:
            if not is_service_healthy(svc):
                log.warning("%s is DOWN", svc["name"])
                restart_service(svc)
            else:
                log.debug("%s is healthy", svc["name"])
        time.sleep(30)
