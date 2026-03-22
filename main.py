from dotenv import load_dotenv
import os
import subprocess
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()

# ── SAFE MODE ────────────────────────────────────────────────────────────────
SAFE_EXT = (".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt")
# main.py — safe() function
def safe(path):
    return (
        path.endswith(SAFE_EXT)
        and "venv" not in path
        and ".git" not in path
        and ".env" not in path  # stops agent touching it
    )

def safe(path):
    return path.endswith(SAFE_EXT) and "venv" not in path and ".git" not in path

# ── TOOLS ────────────────────────────────────────────────────────────────────
@tool
def read_file(path: str) -> str:
    """Read a file."""
    try:
        return open(path).read()
    except Exception as e:
        return f"Error: {e}"

@tool
def write_file(path: str, content: str) -> str:
    """Write to a file."""
    if not safe(path): return "Blocked: unsafe file type."
    open(path, "w").write(content)
    return f"Saved {path}"

@tool
def create_file(path: str, content: str = "") -> str:
    """Create a new file."""
    if not safe(path): return "Blocked: unsafe file type."
    if os.path.exists(path): return "File already exists."
    open(path, "w").write(content)
    return f"Created {path}"

@tool
def delete_file(path: str) -> str:
    """Delete a file."""
    if not safe(path): return "Blocked."
    if not os.path.exists(path): return "File not found."
    os.remove(path)
    return f"Deleted {path}"

@tool
def list_files(directory: str = ".") -> str:
    """List all project files."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ("venv", "__pycache__", "node_modules", ".git")]
        for f in filenames:
            files.append(os.path.join(root, f))
    return "\n".join(files) or "No files found."

@tool
def run_command(command: str) -> str:
    """Run a shell command."""
    blocked = ("rm -rf", "del /f", "format", "shutdown")
    if any(b in command for b in blocked):
        return "Blocked: dangerous command."
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout or result.stderr or "No output."
    except Exception as e:
        return f"Error: {e}"

@tool
def run_file(path: str) -> str:
    """Run a Python file."""
    if not path.endswith(".py"): return "Only .py files."
    try:
        result = subprocess.run(["python", path], capture_output=True, text=True, timeout=30)
        return result.stdout or result.stderr or "No output."
    except Exception as e:
        return f"Error: {e}"

# ── AGENT ────────────────────────────────────────────────────────────────────
llm = ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.getenv("GROQ_API_KEY")
)

agent = create_react_agent(
    model=llm,
    tools=[read_file, write_file, create_file, delete_file, list_files, run_command, run_file],
    checkpointer=MemorySaver(),
    prompt="""
You are an elite coding agent. Be precise and fast.

RULES:
1. Always read_file before editing anything
2. Always write_file or create_file to save changes
3. Fix everything in one pass — no partial fixes
4. Run the file after fixing to verify it works
5. Keep explanations short and clear
""")

config = {"configurable": {"thread_id": "main"}}

# ── RUN ──────────────────────────────────────────────────────────────────────
console.print(Panel("🤖 [bold green]Code Agent Ready[/bold green] | /files  /help  /exit"))

while True:
    try:
        user_input = console.input("\n[cyan]You →[/cyan] ").strip()
    except (KeyboardInterrupt, EOFError):
        break

    if not user_input: continue
    if user_input in ("/exit", "exit", "quit"): break
    if user_input == "/files":
        console.print(list_files.invoke({"directory": "."}))
        continue
    if user_input == "/help":
        console.print("Commands: /files  /exit\nOr just tell me what to fix!")
        continue

    console.print("[yellow]Working...[/yellow]")

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config
        )
        console.print(Panel(result["messages"][-1].content, border_style="green"))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")