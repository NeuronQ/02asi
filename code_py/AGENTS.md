# AGENTS.md — `code_py/`

Instructions for AI coding agents working in this directory. Read this fully
before executing notebook code or editing `02asi.ipynb`.

## 0. Environment facts

- Package/dependency manager is **uv**. Always invoke Python as `uv run python …`
  (or `uv run <tool>`), never a bare `python`. The virtualenv lives in `.venv/`.
- Target interpreter: **Python 3.13** (see `.python-version`, `pyproject.toml`).
- Install/sync deps with `uv sync`. Add deps with `uv add <pkg>` (runtime) or
  `uv add --dev <pkg>` (tooling). Never hand-edit `uv.lock`.
- Shell on this machine: prefer `podman compose …` over `docker-compose …` if
  containers ever become relevant (currently they are not).

## 1. The shared-kernel model (read this first)

The default behavior of notebook tooling is a trap: `jupyter nbconvert --execute`
and most "run the notebook" tools start a **fresh kernel** and execute every cell
top-to-bottom. That destroys in-memory state and recomputes everything. It is the
wrong tool for collaborative, stateful, out-of-order work.

Instead, this project uses **one long-lived kernel hosted by a local Jupyter
server**, which both the human (via Cursor's notebook UI) and the agent (via
`nbkernel.py`) connect to. Consequences you must internalize:

- Variables/imports/loaded data **persist** between your calls and are **shared**
  with the human's UI in both directions.
- You can run **individual cells in any order** (`run-cell <idx>`), or arbitrary
  code (`run-code "…"`), without re-running the whole notebook.
- The kernel is the source of truth for runtime state, **not** the `.ipynb` file.

`nbkernel.py` is the single entrypoint. It manages a JupyterLab server, discovers
the kernel the human's UI is bound to, and talks to that kernel over the Jupyter
messaging protocol via `jupyter_client.BlockingKernelClient`.

## 2. Files and state

- `nbkernel.py` — the CLI (server lifecycle + attach + execute).
- `.nbkernel/` — runtime state, **gitignored**. Do not commit. Contains:
  - `server.json` — `{pid, port (8899), token, url, root_dir}` for the running server.
  - `attach.json` — `{kernel_id, connection_file}` for the currently attached kernel.
  - `server.log` — JupyterLab server log (useful for debugging connections).

## 3. Command reference

All commands are run from `code_py/`:

| Command | Purpose |
| --- | --- |
| `uv run python nbkernel.py serve` | Start the Jupyter server (detached, port 8899, random token). Idempotent: no-op if already running. |
| `uv run python nbkernel.py server-info` | Print `http://localhost:8899/?token=…` for the human to paste into Cursor. |
| `uv run python nbkernel.py attach [--nb 02asi.ipynb]` | Discover and lock onto the kernel the UI is using; writes `attach.json`. |
| `uv run python nbkernel.py status` | Show server + attached-kernel state. |
| `uv run python nbkernel.py list [--nb …]` | List cells: `index  type [exec_count] | first line`. |
| `uv run python nbkernel.py run-code "<code>"` | Execute code in the shared kernel; prints status + outputs. |
| `uv run python nbkernel.py run-cell <idx> [--write]` | Execute one cell's *source* from the `.ipynb` in the kernel. |
| `uv run python nbkernel.py run-cells <i j …> [--write]` | Execute several cells' source in the given order. |
| `uv run python nbkernel.py vars` | List user-defined variable names + types in the kernel. |
| `uv run python nbkernel.py restart-kernel` | Restart the shared kernel (clears all state). |
| `uv run python nbkernel.py stop` | Shut down the server (and all its kernels). |

Optional flags: `--timeout <secs>` (default 120) on the run-* commands.

## 4. Standard operating procedure

### 4.1 Before running any notebook code

1. `uv run python nbkernel.py status`.
2. If `server: not running` → run `serve`, then print the URL (via the `serve`
   output or `server-info`) and ask the human to connect Cursor:
   *Select Kernel → Select Another Kernel… → Existing Jupyter Server… → paste URL
   → pick Python 3 → run one cell.* Wait for them to confirm.
3. If `attached kernel: none` → run `attach`. If it fails, see §5.
4. Verify with a cheap probe: `run-code "print('kernel ok')"`.

### 4.2 Running things

- Prefer `run-code` for inspection, setup, and heavy/auxiliary computation.
- Use `run-cell <idx>` to execute the source of a specific notebook cell. Use
  `list` first to confirm indices (they shift whenever cells are added/removed).
- Report results in chat. Do **not** assume the human sees CLI output in their UI.

### 4.3 Editing notebook cells

- To change a cell's *source*, edit the `.ipynb` with the notebook editing tool,
  then re-run that cell with `run-cell <idx>` so kernel state matches the file.
- **Do not hand-edit cell `outputs` in the `.ipynb` JSON.** The notebook editing
  tool has repeatedly dropped the required `name` field from `stream` outputs,
  producing an invalid notebook (`NotebookValidationError: 'name' is a required
  property`). If you must write outputs programmatically, go through `nbformat`
  (as `run-cell --write` does), which normalizes them.

## 5. Failure modes and recovery

- **`attach` says "No running kernel found"**: the human hasn't connected Cursor
  to the server, or hasn't run a cell yet (the kernel only starts on first run).
  Re-share the URL and the connect steps; confirm `status` shows `connections: 1`
  before retrying. Check `.nbkernel/server.log` — only `/lab` GETs means they
  opened the URL in a browser instead of Cursor's kernel picker.
- **`attach` says "Multiple kernels running"**: the single-kernel fallback can't
  disambiguate. Note that Cursor registers notebooks under a *mangled* session
  path (e.g. `02asi-jvsc-…ipynb`), so name-matching usually won't fire and we rely
  on there being exactly one kernel. Ask the human to close extra kernels, or
  identify the right `kernel_id` from `GET /api/sessions` and set `attach.json`
  accordingly.
- **"Attached kernel is not responding"**: the kernel was restarted/replaced; just
  re-run `attach`.
- **Server URL/token stopped working**: the server was restarted; tokens are
  regenerated per `serve`. Re-share the new URL, have the human reconnect, re-`attach`.
- **You need a clean slate**: `restart-kernel` (keeps the server) or `stop` then
  `serve` (full reset; requires reconnecting Cursor).

## 6. Hard rules

- Never use `nbconvert --execute` (or any "run whole notebook" tool) for stateful
  collaborative work; it spawns a throwaway kernel and recomputes everything.
- Never write to `02asi.ipynb` outputs while the human has it open in Cursor unless
  explicitly asked; pass `--write` only when you know Cursor is not editing it,
  otherwise you'll clash with Cursor's document state.
- Never commit `.nbkernel/`.
- Always use `uv run …`; never a bare `python`.

<!-- Add new agent-facing sections below as the project grows (e.g. coding
     conventions, test commands, data handling, rust interop). Keep this file
     pedantic and unambiguous. -->
