import os
import json
import streamlit as st
import ollama

from tools import AVAILABLE_FUNCTIONS

model = "qwen3:8b"
MAX_TURNS = 5
history_file = "conversation_history.json"

summary_trigger = 12
keep_recent = 6

def _extract_role_and_content(message):
    if isinstance(message,dict):
        return message.get("role"), message.get("content")
    return message.role, message.content

def save_history(messages):
    plain_messages = []
    for m in messages:
        role, content = _extract_role_and_content(m)
        plain_messages.append({"role" : role, "content" : content})
    with open(history_file, 'w', encoding="UTF-8") as f:
        json.dump(plain_messages, f, indent = 2)

def load_history():
    if not os.path.exists(history_file):
        return[]

    with open(history_file, "r", encoding= "UTF-8") as f:
        return json.load(f)

def summarize_older_messages(message_to_summarize):
    lines = []
    for m in message_to_summarize:
        role, content = _extract_role_and_content(m)
        if content:
            lines.append(f"{role}:{content}")

    transcript = "\n".join(lines)

    summary_response = ollama.chat(
        model = model,
        messages = [{
            "role" : "user",
            "content" : ("Summarise the key facts, requests and decisions from this"
                         "conversation in 3-5 sentences, so the summary can replace"
                         "the full message transcript below in the future context. \n\n" + transcript) ,
        }],
    )
    return summary_response.message.content

def maybe_summarize_history(messages):
    if len(messages) <= summary_trigger:
        return messages

    older, recent = messages[:-keep_recent], messages[-keep_recent:]
    summary_text = summarize_older_messages(older)

    summary_message = {
        "role" : "system",
        "content" : f"summary of earlier conversations: {summary_text}"
    } 
    return [summary_message] + recent

def run_agent_turn(user_message, messages):
    messages.append({"role":"user", "content" : user_message})
    messages = maybe_summarize_history(messages)

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

            st.info(f"called '{call.function.name}' with {call.function.arguments}")

            messages.append({
                "role" : "tool",
                "content" : str(result),
                "tool_name": call.function.name,
            })

    return "Stopped after too many tool call rounds", messages

st.title("Local AI Assistant")
st.caption("Running qwen3:8b locally via Ollama")

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

for message in st.session_state.messages:
    role, content = _extract_role_and_content(message)

    if role in ('user', 'assistant') and content:
        with st.chat_message(role):
            st.write(content)

user_input = st.chat_input("Ask me to read or write a file...")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer, st.session_state.messages = run_agent_turn(user_input, st.session_state.messages)

        st.write(answer)

    save_history(st.session_state.messages)

if st.sidebar.button("Clear Conversation"):
    st.session_state.messages = []
    if os.path.exists(history_file):
        os.remove(history_file)
    st.rerun()