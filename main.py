import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

from tools import TOOL_DECLARATIONS, AVAILABLE_FUNCTIONS

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise SystemExit(
        "No GEMINI_API_KEY found. Copy .env.example to .env and add your key."
    )

client = genai.Client(
    http_options=types.HttpOptions(timeout=15_000)
)
model = "gemini-3.8-flash"


def run_agent_turn(user_message, previous_interaction_id):
    """Send one user message to Gemini and handle any tool calls it makes
    along the way. Return(final _answer_text, latest_interaction_id).
    """

    try:
        print("Sending request to Gemini...")
        interaction = client.interactions.create(
            model=model,
            input=user_message,
            tools=TOOL_DECLARATIONS,
            previous_interaction_id=previous_interaction_id,
        )
        print("Got a response.")
    except Exception as e:
        print("ERROR calling Gemini:", repr(e))
        return "Sorry, something went wrong.", previous_interaction_id

    interaction = client.interactions.create(
        model = model,
        input = user_message,
        tools = TOOL_DECLARATIONS,
        previous_interaction_id = previous_interaction_id
    )

    while True:
        function_call_steps = [s for s in interaction.steps if s.type == "function_call"]

        if not function_call_steps:
            return interaction.output_text, interaction.id

        function_results = []
        for step in function_call_steps:
            func = AVAILABLE_FUNCTIONS.get(step.name)
            if func is None:
                result = f"Error: unknown tool '{step.name}"
            else:
                print(f"[tool_call] {step.name}({step.arguments})")
                result = func(**step.arguments)

            function_results.append({
                "type" : "function_result",
                "name" : step.name,
                "call_id" : step.id,
                "result" : [{"type" : "text", "text" : json.dumps(result)}]
            })

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