# asi (Python)

Minimal Python project managed with [uv](https://docs.astral.sh/uv/). Most of the
real work happens in the Jupyter notebook `02asi.ipynb`.

## Quick start

```bash
# from this directory (code_py/)
uv sync            # create .venv and install deps (incl. dev tools)
uv run main.py     # run the tiny entrypoint
```

## Why Python 3.13

3.13 is the newest Python supported by the full ML/AI stack we may add later
(numpy, scipy, scikit-learn, torch, jax, **tensorflow**, hugging face, langchain,
pydantic, pytest). TensorFlow is the limiting factor: its latest stable release
supports up to 3.13 and does not yet support 3.14.

## Working in the notebook with a shared kernel

Normally Cursor's notebook UI and any command-line tooling each spawn their *own*
Python kernel, so they don't see each other's variables. This project ships a
small helper, `nbkernel.py`, that runs a local Jupyter server which **both Cursor
and an AI agent connect to**, so you share one live kernel: variables, imports and
loaded data are visible from both sides, and you can re-run individual cells in any
order without recomputing everything.

If you just want to use the notebook by yourself, you don't need any of this — pick
a normal Python kernel in Cursor and go. The steps below are for the shared
(human + agent) workflow.

### One-time setup per session

```bash
uv run python nbkernel.py serve         # start the Jupyter server (prints a URL)
uv run python nbkernel.py server-info   # reprint the URL+token if you lost it
```

Then connect Cursor to that same server:

1. Open `02asi.ipynb`.
2. Click the **kernel selector** (top-right of the notebook).
3. **Select Another Kernel… → Existing Jupyter Server…**
4. Choose *Enter the URL of the running Jupyter Server* and paste the URL printed
   by `serve` (looks like `http://localhost:8899/?token=…`).
5. Pick the **Python 3 (ipykernel)** kernel.
6. **Run any one cell** — this actually starts the kernel on the server.

> Pick *Existing Jupyter Server*, not *Python Environments*. Don't paste the URL
> into a web browser; it goes into Cursor's kernel picker.

The agent then runs `uv run python nbkernel.py attach` to lock onto the kernel
Cursor created. From that point you share state in both directions.

### Everyday commands

```bash
uv run python nbkernel.py status                 # server + attached kernel
uv run python nbkernel.py list                   # list notebook cells with indices
uv run python nbkernel.py run-code "print(x)"    # run code in the shared kernel
uv run python nbkernel.py run-cell 4 --write     # run cell 4's source; write output back to the .ipynb
uv run python nbkernel.py vars                   # list variables defined in the kernel
uv run python nbkernel.py restart-kernel         # clear all state
uv run python nbkernel.py stop                   # shut the server down
```

Runtime files (server PID, token, logs) live in `.nbkernel/` and are gitignored.

### Good to know

- **Restarting the server** invalidates the URL/token: reconnect Cursor's kernel
  picker and have the agent re-`attach`.
- **Outputs**: by default the agent runs cells with `--write`, persisting outputs
  back into `02asi.ipynb` so you can see them in Cursor's notebook UI. It only runs
  without `--write` (reporting output in chat only) if you ask it to. In practice
  this coexists fine with the notebook open in Cursor; if an output doesn't appear,
  reload the file when Cursor reports it changed on disk.
- **One kernel at a time** is the happy path. If several kernels are running on the
  server, `attach` can't tell which notebook is yours — close extras or tell the
  agent which one to use.

See [`AGENTS.md`](./AGENTS.md) for the precise, step-by-step protocol an AI agent
should follow.

## Project layout

```
code_py/
├── 02asi.ipynb     # main notebook
├── main.py         # tiny entrypoint
├── nbkernel.py     # shared-kernel helper (Jupyter server + CLI)
├── src/asi/        # package code
├── pyproject.toml  # deps, managed by uv
└── AGENTS.md       # agent-facing instructions
```

<!-- Add new sections below as the project grows (e.g. Testing, Architecture,
     Datasets, Benchmarks). Keep human docs here concise; put detailed agent
     protocol in AGENTS.md. -->

## Testing

_TODO._

## Notes

_TODO._
