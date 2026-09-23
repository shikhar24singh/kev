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

    target = None
    workerw = win32gui.FindWindowEx(0, 0, "WorkerW", None)
    while workerw:
        owns_icons = win32gui.FindWindowEx(workerw, 0, "SHELLDLL_DefView", None)
        if owns_icons:
            print(f"Found icon-owning WorkerW: {workerw}")
            target = win32gui.FindWindowEx(0, workerw, "WorkerW", None)
            break
        workerw = win32gui.FindWindowEx(0, workerw, "WorkerW", None)

    if not target:
        owns_icons = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None)
        if owns_icons:
            print("Progman owns the icons directly — parenting into Progman.")
            target = progman

    if target:
        win32gui.SetParent(root.winfo_id(), target)
    else:
        print("Warning: couldn't find the desktop layer - widget will work as a normal window instead")

root = tk.Tk()
root.title("Assistant Widget")
root.geometry("380x420+900+500")
root.overrideredirect(True)
embed_into_desktop(root)
root.withdraw()
root.attributes("-alpha", "0.85")

drag_bar = tk.Frame(root, bg = "#000000", height = 26)
drag_bar.pack(fill = 'x', side = "top")
drag_bar.pack_propagate(False)

drag_label = tk.Label(drag_bar, text = "Assistant Widget", bg = "#000000", fg = "white")
drag_label.pack(side = "left", padx = 8)

close_button = tk.Label(drag_bar, text = 'X', bg = "#000000", fg = "white", cursor = "hand2")
close_button.pack(side = "right", padx = 8)
close_button.bind("<Button-1>", lambda event: root.destroy())



_drag_data = {"x" : 0, "y" : 0}

def start_drag(event):
    _drag_data['x'] = event.x
    _drag_data['y'] = event.y

def do_drag(event):
    new_x = root.winfo_x() + (event.x - _drag_data["x"])
    new_y = root.winfo_y() + (event.y - _drag_data["y"])
    root.geometry(f"+{new_x}+{new_y}")

drag_bar.bind("<Button-1>", start_drag)
drag_bar.bind("<B1-Motion>", do_drag)
drag_label.bind("<Button-1>", start_drag)
drag_label.bind("<B1-Motion>", do_drag)

chat_display = tk.Text(root, wrap="word", state="disabled", bg="#1e1e1e", fg="white")
chat_display.pack(expand=True, fill="both", padx=8, pady=8)

entry = tk.Entry(root)
entry.pack(fill="x", padx=8, pady=(0, 8))

def append_to_display(text):
    chat_display.config(state="normal")
    chat_display.insert("end", text + "\n\n")
    chat_display.config(state="disabled") 
    chat_display.see("end")

def on_submit(event=None):
    global messages
    user_text = entry.get().strip()
    if not user_text:
        return
    entry.delete(0, "end")
    append_to_display(f"You: {user_text}")

    root.update()
    answer, messages = run_agent_turn(user_text, messages)
    append_to_display(f"Assistant: {answer}")

entry.bind("<Return>", on_submit)

def toggle_window():
    if root.state() == "withdrawn":
        root.deiconify()
        root.after(100, lambda: entry.focus_force())
    else:
        root.withdraw()

    keyboard.add_hotkey(hotkey, toggle_window)

root.mainloop()