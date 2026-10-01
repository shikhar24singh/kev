from datetime import datetime
from dataclasses import dataclass

import ollama
from tools import AVAILABLE_FUNCTIONS, apply_file_edit

model = "qwen3:8b"

MAX_TURNS = 5
DATE_CONTEXT_MARKER = "Current local date (computer clock):"


@dataclass
class AgentTurnResult:
    answer: str
    messages: list
    pending_edit: dict | None = None


def _refresh_date_context(messages):
    today = datetime.now().astimezone().date().isoformat()
    date_context = (
        f"{DATE_CONTEXT_MARKER} {today}. For questions about today's date, "
        "answer using this date. Do not infer it from your training cutoff or search the web for it. "
        "For edits to existing workspace files, read the complete file with read_file first, "
        "then use edit_file to propose a focused replacement. Do not use write_file to modify "
        "an existing file, and never say an edit was applied before the user approves it."
    )

    for message in messages:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role == "system" and isinstance(message, dict):
            lines = message.get("content", "").splitlines()
            lines = [line for line in lines if not line.startswith(DATE_CONTEXT_MARKER)]
            lines.append(date_context)
            message["content"] = "\n".join(lines)
            return

    messages.insert(0, {"role": "system", "content": date_context})

def run_agent_turn(user_message, messages):
    _refresh_date_context(messages)
    messages.append({"role": "user", "content": user_message})
    return _continue_agent(messages)


def _value(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _successful_read_contents(messages):
    contents_by_filename = {}
    for index, message in enumerate(messages):
        if _value(message, "role") != "assistant":
            continue
        for call in _value(message, "tool_calls", []) or []:
            function = _value(call, "function")
            arguments = _value(function, "arguments", {}) or {}
            filename = arguments.get("filename")
            if _value(function, "name") != "read_file" or not filename:
                continue
            for result in messages[index + 1:]:
                if _value(result, "role") == "assistant":
                    break
                content = _value(result, "content", "")
                if (
                    _value(result, "role") == "tool"
                    and _value(result, "tool_name") == "read_file"
                    and content.startswith(f"FILE READ: {filename}\n")
                ):
                    contents_by_filename[filename] = content[len(f"FILE READ: {filename}\n"):]
    return contents_by_filename


def _continue_agent(messages):

    for turn in range(MAX_TURNS):
        print(f"  (turn {turn + 1}) sending to local model...")
        response = ollama.chat(
            model=model,
            messages=messages,
            tools=list(AVAILABLE_FUNCTIONS.values()),
        )
        print("  (got a response)")
        print("  tool_calls:", response.message.tool_calls)
        print("  content:", repr(response.message.content))

        read_contents = _successful_read_contents(messages)
        messages.append(response.message)
        tool_calls = response.message.tool_calls

        if not tool_calls:
            return AgentTurnResult(response.message.content or "", messages)

        pending_edit = None
        for call in tool_calls:
            function_name = call.function.name
            arguments = call.function.arguments
            func = AVAILABLE_FUNCTIONS.get(function_name)
            if func is None:
                result = f"Error: unknown tool '{function_name}'"
            elif function_name == "edit_file" and arguments.get("filename", "") not in read_contents:
                result = (
                    f"Error: read the complete file '{arguments.get('filename', '')}' with "
                    "read_file and review its contents before proposing an edit."
                )
            else:
                print(f"  [tool call] {function_name}({arguments})")
                result = func(**arguments)

                if function_name == "read_file" and isinstance(result, str) and not result.startswith("Error:"):
                    result = f"FILE READ: {arguments['filename']}\n{result}"
                elif (
                    isinstance(result, dict)
                    and result.get("status") == "edit_proposal"
                    and read_contents.get(result["filename"]) != result["original_content"]
                ):
                    result = (
                        f"Error: '{result['filename']}' changed since it was read. "
                        "Read the complete file again before preparing a new proposal."
                    )

            if isinstance(result, dict) and result.get("status") == "edit_proposal":
                if pending_edit is None:
                    pending_edit = {"proposal": result, "tool_result_index": None}
                    result_for_model = (
                        "The proposed edit is waiting for user review. No file was changed."
                    )
                else:
                    result_for_model = "Only one file edit can be reviewed at a time."
            else:
                result_for_model = str(result)

            messages.append({
                "role": "tool",
                "content": result_for_model,
                "tool_name": function_name,
            })
            if isinstance(result, dict) and result.get("status") == "edit_proposal" and pending_edit:
                if pending_edit["tool_result_index"] is None:
                    pending_edit["tool_result_index"] = len(messages) - 1

        if pending_edit:
            return AgentTurnResult("", messages, pending_edit)

    return AgentTurnResult("Stopped after too many tool-call rounds — see debug output above.", messages)


def resolve_pending_edit(pending_edit, approved, messages):
    proposal = pending_edit["proposal"]
    result_index = pending_edit["tool_result_index"]
    result = apply_file_edit(proposal) if approved else (
        f"The user declined the proposed edit to '{proposal['filename']}'. No changes were made."
    )
    messages[result_index]["content"] = result
    return _continue_agent(messages)


def main():
    print("Local File Assistant ready (qwen3:8b). Type 'exit' to quit.\n")
    messages = [{
        "role" : "system",
        "content" : "Never use emojis in replies. Use web search for current or recent events. "
                    "Never use em-dashes. For edits to existing workspace files, read the "
                    "complete file with read_file first, then use edit_file to propose a "
                    "focused replacement. Do not use write_file to modify an existing file. "
                    "Never say an edit was applied before the user approves it."
    }]

    while True:
        user_input = input('You: ').strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        result = run_agent_turn(user_input, messages)
        while result.pending_edit:
            proposal = result.pending_edit["proposal"]
            print(f"\nProposed changes to {proposal['filename']}:\n")
            print(proposal["diff"])
            approved = input("Apply these changes? Type 'yes' to approve: ").strip().lower() == "yes"
            result = resolve_pending_edit(result.pending_edit, approved, result.messages)
        messages = result.messages
        print(f"\nAssistant: {result.answer}\n")


if __name__ == "__main__":
    main()
