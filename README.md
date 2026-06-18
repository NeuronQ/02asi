# 02asi

A learning/experiments monorepo. Today it contains a Python project; it's
structured so other languages (e.g. a Rust counterpart for multilingual
Python+Rust work) can be added alongside later.

## Layout

```
02asi/
├── code_py/        # Python project (uv-managed) + the 02asi.ipynb notebook
│   ├── README.md   # how to use the Python project
│   └── AGENTS.md   # agent protocol (shared-kernel notebook workflow, etc.)
└── README.md       # you are here
```

## Getting started

Most work currently lives in `code_py/`. From the repo root:

```bash
cd code_py
uv sync
uv run main.py
```

## Working in the notebook (human + agent shared kernel)

`code_py/` includes `nbkernel.py`, a helper that lets Cursor's notebook UI and an
AI agent share **one live Jupyter kernel**, so state is visible from both sides and
cells can be re-run individually in any order. See
[`code_py/README.md`](./code_py/README.md) for the human walkthrough and
[`code_py/AGENTS.md`](./code_py/AGENTS.md) for the detailed agent protocol.

## Running agents: from root vs from `code_py/`

This repo supports both working styles:

- **From `code_py/`** — if you only care about the Python project, treat `code_py/`
  as your working directory. Its `AGENTS.md` is the authoritative guide and all
  `uv run …` commands assume that directory.
- **From the repo root** — if you're doing cross-cutting or multilingual work,
  run agents from here. The root [`AGENTS.md`](./AGENTS.md) orients you and points
  into each subproject's own `AGENTS.md`. Remember that Python commands must be run
  inside `code_py/` (e.g. `cd code_py && uv run …`), since that's where the uv
  project and `.venv` live.

<!-- Add new top-level sections / subprojects below as the repo grows
     (e.g. code_rust/, shared tooling, CI). -->
