from pathlib import Path
import ast
import operator


WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok = True)

def _resolve_safe_path(filename: str) -> Path:
    target = (WORKSPACE_DIR/filename).resolve()
    workspace_resolved = WORKSPACE_DIR.resolve()

    if target != workspace_resolved and workspace_resolved not in target.parents:
        raise ValueError(f"'{filename}' is outside the allowed workspace folder.")

    return target

def read_file(filename: str) -> str:
    path = _resolve_safe_path(filename)
    if not path.exists():
        return f"Error: '{filename}' does not exist in the workspace."
    return path.read_text(encoding="utf-8")

def write_file(filename: str, content: str) -> str:
    path = _resolve_safe_path(filename)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to '{filename}'."

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

    path = _resolve_safe_path(filename)
    if not path.exists:
        return f"Error: {filename} does not exist in the agent workspace."

    path.unlink()
    return f"Deleted '{filename}'."



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
        "Write text function to a file in the agent's workspace folder"
        "Overwrite the file if it already exists."
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

AVAILABLE_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "calculate": calculate,
    "delete_file": delete_file
}

TOOL_DECLARATIONS = [read_file_declaration, write_file_declaration]