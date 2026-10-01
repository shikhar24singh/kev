from pathlib import Path
import ast
import difflib
import operator
from ddgs import DDGS


WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok = True)

def _resolve_safe_path(filename: str) -> Path:
    target = (WORKSPACE_DIR/filename).resolve()
    workspace_resolved = WORKSPACE_DIR.resolve()

    if target != workspace_resolved and workspace_resolved not in target.parents:
        raise ValueError(f"'{filename}' is outside the allowed workspace folder.")

    return target

def read_file(filename: str) -> str:
    try:
        path = _resolve_safe_path(filename)
    except Exception as e:
        return f"Error: {e}"
    if not path.exists():
        return f"Error: '{filename}' does not exist in the workspace."
    return path.read_text(encoding="utf-8")

def write_file(filename: str, content: str) -> str:
    try:
        path = _resolve_safe_path(filename)
    except Exception as e:
        return f"Error: {e}"
    try:
        with path.open("x", encoding="utf-8") as new_file:
            new_file.write(content)
    except FileExistsError:
        return (
            f"Error: '{filename}' already exists. Read the complete file and use edit_file "
            "to prepare a replacement for user approval."
        )
    return f"Wrote {len(content)} characters to '{filename}'."


def edit_file(filename: str, search_text: str, replacement_text: str):
    """Propose replacing one exact, unique portion of a workspace file.

    The proposal is shown to the user for approval before anything is written.

    Args:
        filename: File in the agent workspace.
        search_text: Exact text to replace, copied from the file contents.
        replacement_text: New text to put in its place.
    """
    try:
        path = _resolve_safe_path(filename)
    except ValueError as exc:
        return f"Error: {exc}"
    if not path.is_file():
        return f"Error: '{filename}' is not an existing file in the workspace."
    if not search_text:
        return "Error: search_text must be a non-empty exact portion of the file."

    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return f"Error: could not read '{filename}': {exc}"

    occurrences = original.count(search_text)
    if occurrences != 1:
        return (
            f"Error: the exact search text occurs {occurrences} times in '{filename}'. "
            "Choose a longer, unique portion from the complete file contents."
        )

    updated = original.replace(search_text, replacement_text, 1)
    if updated == original:
        return "No changes proposed because the replacement is identical to the existing text."
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )
    return {
        "status": "edit_proposal",
        "filename": filename,
        "original_content": original,
        "updated_content": updated,
        "diff": diff,
    }


def apply_file_edit(proposal: dict) -> str:
    """Apply an approved proposal only if the file is still unchanged."""
    try:
        filename = proposal["filename"]
        path = _resolve_safe_path(filename)
        if not path.is_file():
            return f"Error: '{filename}' no longer exists as a file."
        current = path.read_text(encoding="utf-8")
        if current != proposal["original_content"]:
            return (
                f"Error: '{filename}' changed after the proposal was prepared. "
                "No changes were applied; read the file again and prepare a fresh proposal."
            )
        path.write_text(proposal["updated_content"], encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Error: could not apply the edit to '{filename}': {exc}"
    return f"Applied the approved edit to '{filename}'."

def list_files() -> str:
    files = [p.name for p in WORKSPACE_DIR.iterdir() if p.is_file()]
    if not files:
        return "The workspace is currently empty"
    return "\n".join(files)

_allowed_ops = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _allowed_ops:
        return _allowed_ops[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _allowed_ops:
        return _allowed_ops[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported or unsafe expression.")

def calculate(expression: str) ->str:
    try:
        parsed = ast.parse(expression, mode = "eval").body
        result = _safe_eval(parsed)
        return str(result)
    except Exception:
        return f"Error: could not evaluate '{expression}' as a math expression."

def delete_file(filename: str, confirm: bool = False) -> str:
    if not confirm:
        return (
            f"Refusing to delete '{filename}' without confirmation. "
            "Ask the user to confirm, then call this again with confirm=true."
        )
    try:
        path = _resolve_safe_path(filename)
    except ValueError as e:
        return f"Error: {e}"
    if not path.exists:
        return f"Error: {filename} does not exist in the agent workspace."

    path.unlink()
    return f"Deleted '{filename}'."

def web_search(query: str) -> str:
    """Search the live web for current, up-to-date information. Always use
    this instead of answering from memory for anything involving recent
    events, today's date, current prices, or facts that may have changed
    since training.

    Args:
        query: The search query, e.g. 'latest Python version'
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results = 5))
    except Exception as e:
        return f"Error! web saearch failed."

    if not results:
        return "No results found."

    lines = []
    for r in results:
        snippet = r.get("body", "")[:200]
        lines.append(f"{r['title']}\n{r['href']}\n{snippet}")

    return "\n\n".join(lines)


read_file_declaration = {
    "type" : "function",
    "name" : "read_file",
    "description" : "Read and return the text content of a file in the agent's workspace folder",
    "parameters" : {
        "type" : "object",
        "properties" : {
            "filename" : {
                "type" : "string",
                "name" : "Name of the file to read e.g. 'notes.txt'",
            },
        },
        "required": ["filename"],
    },
}


write_file_declaration = {
    "type" : "function",
    "name" : "write_file",
    "description" : (
        "Create a new text file in the agent's workspace folder. This tool refuses to "
        "overwrite existing files; use edit_file to propose a reviewed change instead."
    ),
    "parameters" : {
        "type" : "object",
        "properties" : {
            "filename" : {
                "type" : "string",
                "description" : "Name of the file to write, e.g. 'Notes.txt'",
            },
            "content" : {
                "type" : "string",
                "description" : "The text content to write into the file",
            },
        },
        "required" : ["filename", "content"],
    },
}

edit_file_declaration = {
    "type": "function",
    "name": "edit_file",
    "description": (
        "Propose replacing one exact unique portion of an existing workspace file. "
        "Read the entire file first with read_file. This only prepares a diff; it never "
        "writes the change until the user reviews and approves it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Workspace-relative file path."},
            "search_text": {"type": "string", "description": "Exact unique text copied from the file."},
            "replacement_text": {"type": "string", "description": "Replacement text."},
        },
        "required": ["filename", "search_text", "replacement_text"],
    },
}

AVAILABLE_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_files": list_files,
    "calculate": calculate,
    "delete_file": delete_file,
    "web_search" : web_search
}

TOOL_DECLARATIONS = [read_file_declaration, write_file_declaration, edit_file_declaration]
