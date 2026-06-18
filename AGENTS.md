# AGENTS.md — repo root

Orientation for AI coding agents working anywhere in the `02asi` repo. This file
is intentionally short; the authoritative, detailed instructions live in each
subproject.

## Repo shape

```
02asi/
└── code_py/   # Python project (uv) + 02asi.ipynb notebook  → see code_py/AGENTS.md
```

More subprojects (e.g. a Rust counterpart) may be added later; each will carry its
own `AGENTS.md`.

## Where to look

- **Python work / the notebook / the shared-kernel workflow:**
  read and follow [`code_py/AGENTS.md`](./code_py/AGENTS.md). It is authoritative
  for everything under `code_py/`.

## Rules that apply repo-wide

- The Python project is **uv-managed and lives in `code_py/`**, not at the root.
  Run Python commands from there: `cd code_py && uv run …`. There is no `uv`
  project at the repo root.
- Use `uv run …`, never a bare `python`.
- On this machine prefer `podman compose …` over `docker-compose …`.
- Don't commit runtime/state dirs such as `code_py/.nbkernel/`.

## Picking a working directory

- Doing only Python? Work from `code_py/` and use its `AGENTS.md` directly.
- Doing cross-cutting / multilingual work? Work from the root, but still defer to
  the relevant subproject's `AGENTS.md` for that subproject's commands and
  conventions.

<!-- Add cross-cutting agent guidance below as the repo grows (e.g. shared
     conventions, multi-language build/test orchestration, CI). Keep
     subproject-specific detail in that subproject's AGENTS.md. -->
