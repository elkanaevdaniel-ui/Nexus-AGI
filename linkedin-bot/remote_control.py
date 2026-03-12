"""
remote_control.py — Remote Terminal & File Editing via Telegram
Provides /run, /edit, /view commands with safety confirmations.
"""
import asyncio
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# ── Safety Configuration ──────────────────────────────────────────────────────

# Commands that require confirmation before execution
DANGEROUS_COMMANDS = [
    "rm ", "rm -", "rmdir", "dd ", "mkfs",
    "kill ", "killall", "pkill",
    "shutdown", "reboot", "halt", "poweroff",
    "systemctl stop", "systemctl disable",
    "iptables -F", "iptables -X",
    "git push --force", "git reset --hard",
    "chmod 777", "chown",
    "> /dev/", ">/dev/",
    "curl | sh", "curl | bash", "wget | sh",
    "pip uninstall", "apt remove", "apt purge",
    "DROP TABLE", "DELETE FROM", "TRUNCATE",
]

# Commands that are completely blocked
BLOCKED_COMMANDS = [
    ":(){ :|:& };:",  # fork bomb
    "cat /etc/shadow",
    "passwd",
    "su -", "su root",
    "sudo su",
]

# Maximum output length to send via Telegram
MAX_OUTPUT_LENGTH = 3500
MAX_FILE_SIZE = 50000  # 50KB max for file viewing

# Allowed base directory for file operations
BASE_DIR = Path("/home")


def is_command_safe(command: str) -> tuple:
    """
    Check if a command is safe to run.
    Returns: (is_safe, needs_confirmation, reason)
    """
    cmd_lower = command.lower().strip()

    # Check blocked commands
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return False, False, f"Blocked: '{blocked}' is not allowed"

    # Check dangerous commands
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous.lower() in cmd_lower:
            return True, True, f"Requires confirmation: contains '{dangerous.strip()}'"

    return True, False, "OK"


async def execute_command(command: str, timeout: int = 30, cwd: str = None) -> dict:
    """
    Execute a shell command safely.
    Returns: {"output": str, "return_code": int, "error": str}
    """
    if cwd is None:
        cwd = str(Path.home() / "ai-projects" / "workdir")

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")

        # Truncate if too long
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + f"\n... (truncated, {len(output)} chars total)"
        if len(error) > MAX_OUTPUT_LENGTH:
            error = error[:MAX_OUTPUT_LENGTH] + f"\n... (truncated)"

        return {
            "output": output,
            "return_code": proc.returncode,
            "error": error,
        }
    except asyncio.TimeoutError:
        return {
            "output": "",
            "return_code": -1,
            "error": f"Command timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "output": "",
            "return_code": -1,
            "error": str(exc),
        }


def view_file(filepath: str) -> dict:
    """
    Read a file and return its contents.
    Returns: {"content": str, "size": int, "error": str}
    """
    try:
        path = Path(filepath).resolve()

        # Security: only allow files under /home
        if not str(path).startswith(str(BASE_DIR)):
            return {"content": "", "size": 0, "error": "Access denied: can only view files under /home"}

        if not path.exists():
            return {"content": "", "size": 0, "error": f"File not found: {filepath}"}

        if not path.is_file():
            return {"content": "", "size": 0, "error": f"Not a file: {filepath}"}

        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            # Read first and last portions
            with open(path, "r", errors="replace") as f:
                content = f.read(MAX_FILE_SIZE // 2)
            content += f"\n\n... (file too large: {size} bytes, showing first {MAX_FILE_SIZE // 2} bytes)"
            return {"content": content, "size": size, "error": ""}

        with open(path, "r", errors="replace") as f:
            content = f.read()

        return {"content": content, "size": size, "error": ""}

    except Exception as exc:
        return {"content": "", "size": 0, "error": str(exc)}


def edit_file(filepath: str, content: str) -> dict:
    """
    Write content to a file.
    Returns: {"success": bool, "error": str}
    """
    try:
        path = Path(filepath).resolve()

        # Security: only allow files under /home
        if not str(path).startswith(str(BASE_DIR)):
            return {"success": False, "error": "Access denied: can only edit files under /home"}

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Backup original if exists
        if path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            import shutil
            shutil.copy2(path, backup)

        with open(path, "w") as f:
            f.write(content)

        return {"success": True, "error": ""}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


def list_directory(dirpath: str = None) -> dict:
    """List files in a directory."""
    if dirpath is None:
        dirpath = str(Path.home() / "ai-projects" / "workdir")

    try:
        path = Path(dirpath).resolve()
        if not str(path).startswith(str(BASE_DIR)):
            return {"files": [], "error": "Access denied"}

        if not path.is_dir():
            return {"files": [], "error": "Not a directory"}

        files = []
        for item in sorted(path.iterdir()):
            stat = item.stat()
            files.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": stat.st_size if item.is_file() else 0,
            })

        return {"files": files, "error": ""}

    except Exception as exc:
        return {"files": [], "error": str(exc)}
