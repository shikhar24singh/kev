"""
Sends the raw user message to Gemini to clean up phrasing and flag whether
it needs current/real-time information, before handing it to the local
model. This is the ONLY part of each turn that touches the internet or
Gemini — the local model still does all the actual tool execution
(reading, writing, deleting files, calculating), so this step can never
access your filesystem, only rewrite text.
"""
 
import os
from dotenv import load_dotenv
from google import genai
 
load_dotenv()
 
if not os.getenv("GEMINI_API_KEY"):
    raise SystemExit("No GEMINI_API_KEY found. Copy .env.example to .env and add your key.")
 
gemini_client = genai.Client()
GEMINI_MODEL = "gemini-3.8-flash"
 
OPTIMIZER_INSTRUCTION = (
    "Rewrite the following user request to be clear and explicit for another "
    "AI assistant to act on. If the request is short or ambiguous (like a "
    "single word or number) and the assistant's previous message offered "
    "choices or asked a question, resolve it into a full, standalone "
    "instruction using that context — don't just pass along a bare reply. "
    "If it requires current, real-time, or recently-changed information, "
    "explicitly note that. Return only the rewritten request, nothing else."
)
 
 
def optimize_prompt(user_message, last_assistant_message = None):
    """
    Returns a cleaned-up version of user_message via Gemini. If Gemini is
    unreachable (no internet, quota issue, etc.), falls back to the
    original message instead of breaking the whole agent.
    """
    context_block = ""
    if last_assistant_message:
        context_block = (
            f"The assistant's previous message was:\n{last_assistant_message}\n\n"
        )
    try:
        interaction = gemini_client.interactions.create(
            model=GEMINI_MODEL,
            input=f"{context_block} {OPTIMIZER_INSTRUCTION}\n\nRequest: {user_message}",
        )
        return interaction.output_text.strip()
    except Exception as e:
        print(f"  (prompt optimization failed, using original message: {e})")
        return user_message