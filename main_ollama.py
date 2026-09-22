import ollama
from tools import AVAILABLE_FUNCTIONS

model = "qwen3:8b"

MAX_TURNS = 5

def run_agent_turn(user_message, messages):
    messages.append({"role": "user", "content": user_message})

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

        messages.append(response.message)
        tool_calls = response.message.tool_calls

        if not tool_calls:
            return response.message.content, messages

        for call in tool_calls:
            func = AVAILABLE_FUNCTIONS.get(call.function.name)
            if func is None:
                result = f"Error: unknown tool '{call.function.name}'"
            else:
                print(f"  [tool call] {call.function.name}({call.function.arguments})")
                result = func(**call.function.arguments)

            messages.append({
                "role": "tool",
                "content": str(result),
                "tool_name": call.function.name,
            })

    return "Stopped after too many tool-call rounds — see debug output above.", messages


def main():
    print("Local File Assistant ready (qwen3:8b). Type 'exit' to quit.\n")
    messages = []

    while True:
        user_input = input('You: ').strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        answer, messages = run_agent_turn(user_input, messages)
        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()