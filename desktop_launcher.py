"""Start Ollama when needed, then open the Kev desktop widget."""

import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
WIDGET_FILE = PROJECT_DIR / "desktop_widget.py"


def ollama_is_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1):
            return True
    except OSError:
        return False


def start_ollama_if_needed():
    if ollama_is_running():
        return None
    process = subprocess.Popen(
        ["ollama", "serve"],
        cwd=PROJECT_DIR,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if ollama_is_running():
            return process
        if process.poll() is not None:
            raise RuntimeError("Ollama exited before its local service became available.")
        time.sleep(1)
    process.terminate()
    raise RuntimeError("Ollama did not start within 30 seconds.")


def main():
    if not WIDGET_FILE.is_file():
        raise FileNotFoundError(f"Desktop widget not found: {WIDGET_FILE}")
    ollama_process = start_ollama_if_needed()
    try:
        return subprocess.call([sys.executable, str(WIDGET_FILE)], cwd=PROJECT_DIR)
    finally:
        if ollama_process is not None and ollama_process.poll() is None:
            ollama_process.terminate()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Kev AI couldn't start: {exc}", file=sys.stderr)
        input("Press Enter to close...")
        raise SystemExit(1)
