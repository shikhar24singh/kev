import os
import time
import sys
import socket
import subprocess

PROJECT_DIR = r"C:\Users\Lenovo\Documents\AI assistant"

VENV_PYTHON = os.path.join(
    PROJECT_DIR,
    ".venv",
    "Scripts",
    "python.exe"
)

APP_FILE = os.path.join(PROJECT_DIR, "app.py")

STREAMLIT_URL = "http://localhost:8501"

def ollama_is_running():
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1):
            return True
    except OSError:
        return False

def start_ollama():
    if ollama_is_running():
        print("Ollama is already running.")
        return None

    print("Starting Ollama...")

    process = subprocess.Popen(
        ["ollama", "serve"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    for _ in range(30):
        if ollama_is_running():
            print("Ollama is ready.")
            return process

        time.sleep(1)

    raise RuntimeError("Ollama failed to start.")

def start_streamlit():
    if not os.path.exists(VENV_PYTHON):
        raise FileNotFoundError(
            f"Virtual environment Python not found:\n{VENV_PYTHON}"
        )

    if not os.path.exists(APP_FILE):
        raise FileNotFoundError(
            f"app.py not found:\n{APP_FILE}"
        )

    print("Starting Streamlit...")

    process = subprocess.Popen(
        [
            VENV_PYTHON,
            "-m",
            "streamlit",
            "run",
            APP_FILE
        ],
        cwd=PROJECT_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    return process

def main():
    print("Starting AI Agent...")
    print()

    start_ollama()

    streamlit_process = start_streamlit()

    print()
    print("AI Agent is running.")
    print("You can close this launcher window.")

    return streamlit_process


if __name__ == "__main__":
    main()