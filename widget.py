import tkinter as tk
import keyboard
import ollama
import win32gui
import win32con

from tools import AVAILABLE_FUNCTIONS

model = "qwen3:8b"
MAX_TURNS = 5
hotkey = "ctrl+alt+a"

summary_trigger = 12
keep_recent = 6

messages = []

def run_agent_turn(user_message, messages):
    messages.append({"role":"user", "content" : user_message})

    for turn in range(MAX_TURNS):
        response = ollama.chat(
            model = model,
            messages = messages,
            tools = list(AVAILABLE_FUNCTIONS.values())
        )
        messages.append(response.message)

        tool_calls = response.message.tool_calls
        if not tool_calls:
            return response.message.content, messages

        for call in tool_calls:
            func = AVAILABLE_FUNCTIONS.get(call.function.name)
            if func is None:
                result = f"Error: Unknown tool called {call.function.name}"
            else:
                result = func(**call.function.arguments)


            messages.append({
                "role" : "tool",
                "content" : str(result),
                "tool_name": call.function.name,
            })

    return "Stopped after too many tool call rounds", messages

def embed_into_desktop(root):
    progman = win32gui.FindWindow("Progman", None)
    win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
    workerw = [None]

    def enum_windows_callback(hwnd, _):
        shell_view = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
        if shell_view !=0:
            workerw[0] = win32gui.FindWindowEx(None, hwnd, "WorkerW", None)

    win32gui.
