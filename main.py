import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
import time

from tools import TOOL_DECLARATIONS, AVAILABLE_FUNCTIONS, apply_file_edit

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise SystemExit(
        "No GEMINI_API_KEY found. Copy .env.example to .env and add your key."
    )

client = genai.Client(
    http_options=types.HttpOptions(timeout=15_000)
)
model = "gemini-3.8-flash"
EDIT_POLICY = (
    "For edits to existing workspace files, read the complete file first, then use edit_file "
    "to propose one focused replacement. Never use write_file to modify an existing file. "
    "Show the exact diff and wait for explicit user approval before applying it."
)


def run_agent_turn(user_message, previous_interaction_id):
    start_time = time.time()
    """Send one user message to Gemini and handle any tool calls it makes
    along the way. Return(final _answer_text, latest_interaction_id).
    """

    try:
        print("Sending request to Gemini...")
        interaction = client.interactions.create(
            model=model,
            input=f"{EDIT_POLICY}\n\nUser request: {user_message}",
            tools=TOOL_DECLARATIONS,
            previous_interaction_id=previous_interaction_id,
        )
        print("Got a response.")
    except Exception as e:
        print("ERROR calling Gemini:", repr(e))
        return "Sorry, something went wrong.", previous_interaction_id

    successful_reads = {}

    while True:
        function_call_steps = [s for s in interaction.steps if s.type == "function_call"]

        if not function_call_steps:
            return interaction.output_text, interaction.id

        function_results = []
        reads_available_before_this_round = dict(successful_reads)
        for step in function_call_steps:
            func = AVAILABLE_FUNCTIONS.get(step.name)
            if func is None:
                result = f"Error: unknown tool '{step.name}"
            elif step.name == "edit_file" and step.arguments.get("filename") not in reads_available_before_this_round:
                result = (
                    f"Error: read the complete file '{step.arguments.get('filename', '')}' first, "
                    "then prepare the edit in a later tool call."
                )
            else:
                print(f"[tool_call] {step.name}({step.arguments})")
                result = func(**step.arguments)

                if step.name == "read_file" and isinstance(result, str) and not result.startswith("Error:"):
                    successful_reads[step.arguments["filename"]] = result
                elif isinstance(result, dict) and result.get("status") == "edit_proposal":
                    if reads_available_before_this_round.get(result["filename"]) != result["original_content"]:
                        result = (
                            f"Error: '{result['filename']}' changed since it was read. "
                            "Read the complete file again before preparing a new proposal."
                        )
                    else:
                        print(f"\nProposed changes to {result['filename']}:\n")
                        print(result["diff"])
                        approved = input("Apply these changes? Type 'yes' to approve: ").strip().lower() == "yes"
                        result = apply_file_edit(result) if approved else (
                            f"The user declined the proposed edit to '{result['filename']}'. No changes were made."
                        )

            function_results.append({
                "type" : "function_result",
                "name" : step.name,
                "call_id" : step.id,
                "result" : [{"type" : "text", "text" : json.dumps(result)}]
            })

        elapsed_time = time.time() - start_time

        print(f"Model replied in {elapsed_time}s")

        interaction = client.interactions.create(
            model = model,
            input = function_results,
            tools = TOOL_DECLARATIONS,
            previous_interaction_id = interaction.id
        )
        print("DEBUG:", interaction.steps)

def main ():
    print("File assistant ready. Type exit to quit. \n")
    previous_id = None

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        answer, previous_id = run_agent_turn(user_input, previous_id)
        print(f"\nAssistant : {answer}\n")

if __name__ == "__main__":
    main()
