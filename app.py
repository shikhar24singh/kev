import os
import json
import streamlit as st
import ollama
import time
from prompt_optimizer import optimize_prompt

from main_ollama import run_agent_turn as run_local_agent_turn, resolve_pending_edit

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
            "content" : ("Summarise the key facts, requests and decisions from this "
                         "conversation in 3-5 sentences, so the summary can replace "
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

def needs_search(user_message):
    response = ollama.chat(
        model = model,
        messages=[{
            "role" : "user",
            "content" : (
                "Does answering this question require current, real-time, "
                "or recently-changed information that you might not know "
                "from training? Answer with only YES or NO.\n\n"
                f"Question: {user_message}"
            )
        }]
    )
    return 'yes' in response.message.content.strip().lower()

def get_last_assistant_content(messages):
    for m in reversed(messages):
        role, content = _extract_role_and_content(m)
        if role == "assistant" and content:
            return content
    return None

def run_agent_turn(user_message, messages):
    last_assistant = get_last_assistant_content(messages)
    optimized_message = optimize_prompt(user_message, last_assistant)
    print(f"Optimized Prompt {optimized_message}")
    user_message = optimized_message
    start_time = time.time()
    if needs_search(user_message):
        user_message += "\n\n(This requires current information - use web search tool to reply to this query)"
    messages = maybe_summarize_history(messages)
    print(f"  (prompt preparation took {time.time() - start_time:.2f} seconds)")
    return run_local_agent_turn(user_message, messages)

st.title("Local AI Assistant")
st.caption("Running qwen3:8b locally via Ollama")

if "messages" not in st.session_state:
    st.session_state.messages = load_history() or [{
        "role" : "system",
        "content" : "Never use emojis in your replies to a query. "
                    "Always use web search tool to answer related to current or recent events. "
                    "Never uses em-dashes in your replies. Read the complete file before editing, "
                    "use edit_file to propose a focused change, and wait for user approval before "
                    "applying it. Never use write_file to modify an existing file."
    }]

for message in st.session_state.messages:
    role, content = _extract_role_and_content(message)

    if role in ('user', 'assistant') and content:
        with st.chat_message(role):
            st.write(content)

user_input = st.chat_input("Ask Kev to read, create, or edit a file...")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            turn_result = run_agent_turn(user_input, st.session_state.messages)
            st.session_state.messages = turn_result.messages

        if turn_result.pending_edit:
            st.session_state.pending_file_edit = turn_result.pending_edit
        else:
            st.write(turn_result.answer)

    save_history(st.session_state.messages)

if st.session_state.get("pending_file_edit"):
    pending = st.session_state.pending_file_edit
    proposal = pending["proposal"]
    st.subheader(f"Review proposed edit: {proposal['filename']}")
    st.code(proposal["diff"], language="diff", line_numbers=False)
    apply_col, reject_col = st.columns(2)
    with apply_col:
        apply_clicked = st.button("Apply changes", type="primary", key="apply_file_edit")
    with reject_col:
        reject_clicked = st.button("Reject", key="reject_file_edit")

    if apply_clicked or reject_clicked:
        approved = apply_clicked
        with st.spinner("Applying approved edit and finishing the response..." if approved else "Finishing the response..."):
            turn_result = resolve_pending_edit(
                pending,
                approved,
                st.session_state.messages,
            )
        st.session_state.messages = turn_result.messages
        st.session_state.pending_file_edit = turn_result.pending_edit
        save_history(st.session_state.messages)
        st.rerun()

if st.sidebar.button("Clear Conversation"):
    st.session_state.messages = []
    if os.path.exists(history_file):
        os.remove(history_file)
    st.rerun()
