# Kev AI

A local-first AI assistant that uses an LLM to understand user requests, call tools, work with files, perform calculations, and search the web. The project supports both **local inference through Ollama** and **cloud inference through Google Gemini**.

## Overview

Kev AI is designed around an agent workflow where the language model can decide when to use available tools instead of simply generating a text response.

The local agent currently uses **Qwen3 8B through Ollama** and supports multiple tool calls across an interaction.

The project also includes a Gemini-based implementation and a Gemini-powered prompt optimization layer. The optimizer rewrites user requests into clearer, standalone instructions before passing them to the local agent.

---

## Features

* Local AI inference with **Ollama**
* Qwen3 8B local agent
* Tool-calling architecture
* File reading and writing
* File listing
* File deletion with confirmation
* Safe mathematical expression evaluation
* Web search using DDGS
* Gemini-powered cloud agent
* Gemini prompt optimization
* Conversation context across agent turns
* Streamlit-based application
* Automatic Ollama and Streamlit launcher
* Windows executable support through PyInstaller

---

## Architecture

The project follows a tool-using agent architecture:

```text
                         User
                           |
                           v
                  +----------------+
                  |    Kev AI      |
                  |  User Interface|
                  +----------------+
                           |
                           v
                  +----------------+
                  |   AI Agent     |
                  |   Qwen3 8B     |
                  +----------------+
                           |
                    Tool Selection
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
     File Tools       Calculator       Web Search
          |                |                |
          v                v                v
      Workspace        Safe AST        DDGS Search
```

The local agent sends the conversation and available tools to Ollama. When the model requests a tool, the corresponding Python function is executed and its result is returned to the model. This process can continue for multiple tool-call rounds, with a maximum of five rounds currently configured.

---

## Available Tools

The agent currently exposes the following functions:

| Tool          | Description                                   |
| ------------- | --------------------------------------------- |
| `read_file`   | Reads a text file from the agent workspace    |
| `write_file`  | Creates or overwrites a file in the workspace |
| `list_files`  | Lists files in the workspace                  |
| `calculate`   | Evaluates supported mathematical expressions  |
| `delete_file` | Deletes a file after explicit confirmation    |
| `web_search`  | Searches the live web for current information |

The available functions are registered in `tools.py`.

### File Security

File operations are restricted to the project's `workspace` directory. Paths are resolved before access, and attempts to escape the workspace are rejected.

File deletion additionally requires a confirmation parameter.

### Safe Calculator

The calculator does not directly execute arbitrary Python code. It parses expressions using Python's AST module and only permits a defined set of arithmetic operations such as addition, subtraction, multiplication, division, powers, and unary negation.

---

## Local AI Agent

The main local agent uses:

* **Ollama**
* **Qwen3 8B**
* Python
* Tool calling

The model is configured as:

```text
qwen3:8b
```

and the agent allows up to five tool-call rounds per user request.

A typical interaction looks like:

```text
User Request
     |
     v
Qwen3 8B
     |
     +----> Direct response
     |
     +----> Tool call
              |
              v
        Python function
              |
              v
        Tool result
              |
              v
          Qwen3 8B
              |
              v
        Final response
```

---

## Gemini Mode

The project also contains a Gemini-based agent implementation.

The Gemini agent uses the Google GenAI SDK and currently specifies:

```text
gemini-3.8-flash
```

It supports the same tool declaration architecture and maintains an interaction ID so that subsequent requests can continue the conversation.

A Gemini API key is required for this mode.

Create a `.env` file and add:

```env
GEMINI_API_KEY=your_api_key_here
```

The application checks for this environment variable before starting the Gemini client.

---

## Prompt Optimization

Kev AI includes a separate prompt optimization layer using Gemini.

Its purpose is to transform short or ambiguous user requests into clearer, standalone instructions before they are passed to the local model.

For example, the optimizer can use the previous assistant message to resolve a short follow-up response into a complete request.

If Gemini is unavailable, the optimizer falls back to the original user message rather than stopping the agent.

The architecture is therefore:

```text
User Request
     |
     v
Gemini Prompt Optimizer
     |
     v
Optimized Request
     |
     v
Local Qwen3 Agent
     |
     v
Tool Execution
     |
     v
Final Response
```

---

## Project Structure

A simplified project structure is:

```text
AI assistant/
│
├── app.py
├── main.py
├── main_ollama.py
├── launcher.py
├── tools.py
├── prompt_optimizer.py
│
├── requirements.txt
├── start_agent.bat
├── Kev AI.spec
│
├── workspace/
│   └── ...
│
└── .env
```

### Important Files

| File                  | Purpose                                    |
| --------------------- | ------------------------------------------ |
| `main.py`             | Gemini-based agent implementation          |
| `main_ollama.py`      | Local Ollama agent                         |
| `tools.py`            | Tool implementations and tool declarations |
| `prompt_optimizer.py` | Gemini-based prompt optimization           |
| `launcher.py`         | Starts Ollama and Streamlit                |
| `app.py`              | Streamlit application                      |
| `requirements.txt`    | Python dependencies                        |
| `start_agent.bat`     | Windows launcher script                    |
| `Kev AI.spec`         | PyInstaller configuration                  |

---

## Requirements

### Software

* Windows
* Python 3.x
* Ollama
* A compatible local Ollama model
* Google Gemini API key if Gemini features are used

The current local implementation is configured for:

```text
Qwen3 8B
```

### Python Dependencies

The project uses packages including:

* `ollama`
* `google-genai`
* `streamlit`
* `ddgs`
* `python-dotenv`
* `pyinstaller`

The complete pinned dependency list is available in `requirements.txt`.

---

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "AI assistant"
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate the Environment

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Command Prompt:

```cmd
.venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Install Ollama

Install Ollama and make sure it is available from the command line.

Pull the configured local model:

```bash
ollama pull qwen3:8b
```

### 6. Configure Gemini

If Gemini functionality is required, create a `.env` file:

```env
GEMINI_API_KEY=your_api_key_here
```

---

## Running the Local Agent

The local agent can be started using:

```bash
python main_ollama.py
```

The application will start an interactive terminal session:

```text
Local File Assistant ready (qwen3:8b).

You:
```

Type `exit` or `quit` to close the agent.

---

## Running the Gemini Agent

The Gemini implementation can be started with:

```bash
python main.py
```

It uses the configured Gemini API key and maintains the interaction context between requests.

---

## Running the Streamlit Application

The project also includes a Streamlit application.

The launcher starts Streamlit using the project's virtual-environment Python interpreter and runs the application from the project directory.

The default address configured by the launcher is:

```text
http://localhost:8501
```

---

## One-Click Launcher

The project includes a launcher that can automatically start the required services.

The launcher:

1. Checks whether Ollama is already running.
2. Starts `ollama serve` if necessary.
3. Waits for Ollama to become available.
4. Starts the Streamlit application.
5. Leaves the application running independently.

This makes it possible to start Kev AI without manually launching each service.

---

## Configuration

The main configuration points are currently located in the Python files.

### Local Model

In `main_ollama.py`:

```text
model = "qwen3:8b"
```

### Agent Tool-Call Limit

```text
MAX_TURNS = 5
```

These settings can be changed to match the desired local setup.

---

## Web Search

Kev AI includes a web-search tool based on DDGS.

The search tool is intended for information that may have changed recently, including current events, current prices, and other time-sensitive information. It returns search result titles, URLs, and snippets to the agent.

---

## Safety and Restrictions

Kev AI includes several implementation-level restrictions.

### Workspace Isolation

File operations are limited to the `workspace` directory. Attempts to access paths outside this directory are rejected.

### Delete Confirmation

The delete tool refuses to delete a file unless confirmation is explicitly provided.

### Restricted Calculator

The calculator only supports explicitly permitted AST operations instead of evaluating arbitrary Python expressions.

---

## Building a Windows Executable

The project includes a PyInstaller specification file:

```text
Kev AI.spec
```

and PyInstaller is included in the project's dependencies.

This allows the project to be packaged as a Windows executable without requiring the user to manually run the Python entry point.

---

## Current Limitations

The current implementation has several areas that can be improved:

* The local model's reasoning/tool-call behavior can result in multiple inference rounds.
* Gemini functionality requires an API key and internet connectivity.
* The local agent depends on Ollama and a locally available model.
* The current tool set is relatively small and can be expanded.
* The project currently contains multiple interfaces and execution modes that could eventually be unified.

---

## Future Improvements

Potential future development includes:

* User verification before modifying or deleting files
* More advanced file editing capabilities
* Improved agent planning and verification
* Better conversation-memory management
* Additional tools and integrations
* More robust error handling
* Streaming model responses
* Configurable model selection
* More complete packaging and distribution
* Better separation between planning, verification, and execution

---

## Tech Stack

| Category    | Technology        |
| ----------- | ----------------- |
| Assistant   | **Kev AI**        |
| Language    | Python            |
| Local LLM   | Ollama + Qwen3 8B |
| Cloud LLM   | Google Gemini     |
| UI          | Streamlit         |
| Web Search  | DDGS              |
| Environment | python-dotenv     |
| Packaging   | PyInstaller       |

---

## Project Status

**Kev AI** is actively being developed as a personal AI-agent system focused on combining local LLM inference with practical tools and a Streamlit interface.

The current implementation supports local tool calling, file operations, calculations, web search, Gemini integration, prompt optimization, and automated application startup.

---

## License

Shikhar Singh
Ajay Kumar Garg Engineering College