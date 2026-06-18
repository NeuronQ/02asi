#!/usr/bin/env python
"""Shared-kernel notebook driver.

Runs a local Jupyter server so that BOTH Cursor's native notebook UI and this
CLI connect to the *same* live kernel. State (variables, imports, loaded data)
is therefore shared in both directions: cells you run with Cursor's "Run cell"
button and code I run here hit one and the same kernel.

Typical flow:
    1. python nbkernel.py serve            # start the Jupyter server (once)
    2. python nbkernel.py server-info      # prints the URL+token to paste in Cursor
       -> In Cursor: open the notebook, "Select Kernel" -> "Existing Jupyter
          Server..." -> paste the URL -> pick the Python kernel.
    3. python nbkernel.py attach           # discover the kernel Cursor is using
    4. python nbkernel.py run-code "..."   # run code in that shared kernel
       python nbkernel.py run-cell <idx>   # run a notebook cell's source

Other commands:
    status | list | run-cells <i j ...> | vars | restart-kernel | stop
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from queue import Empty

import nbformat
from jupyter_client import BlockingKernelClient
from jupyter_client.connect import find_connection_file

HERE = Path(__file__).resolve().parent
STATE_DIR = HERE / ".nbkernel"
SERVER_FILE = STATE_DIR / "server.json"
ATTACH_FILE = STATE_DIR / "attach.json"
LOG_FILE = STATE_DIR / "server.log"
DEFAULT_NB = HERE / "02asi.ipynb"
PORT = 8899


# --------------------------------------------------------------------------- #
# jupyter server lifecycle
# --------------------------------------------------------------------------- #
def _server_info() -> dict | None:
    if not SERVER_FILE.exists():
        return None
    info = json.loads(SERVER_FILE.read_text())
    pid = info.get("pid")
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return info


def serve() -> dict:
    info = _server_info()
    if info:
        return info

    STATE_DIR.mkdir(exist_ok=True)
    token = secrets.token_hex(16)
    log = open(LOG_FILE, "ab")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "jupyterlab",
            "--no-browser",
            f"--port={PORT}",
            f"--IdentityProvider.token={token}",
            f"--ServerApp.root_dir={HERE}",
            "--ServerApp.open_browser=False",
        ],
        stdout=log,
        stderr=log,
        cwd=str(HERE),
        start_new_session=True,
    )
    info = {
        "pid": proc.pid,
        "port": PORT,
        "token": token,
        "url": f"http://localhost:{PORT}/",
        "root_dir": str(HERE),
    }
    SERVER_FILE.write_text(json.dumps(info, indent=2))

    # Wait for the REST API to come up.
    for _ in range(60):
        try:
            _rest(info, "/api/status")
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    else:
        sys.exit("Jupyter server did not come up; check .nbkernel/server.log")
    return info


def stop() -> bool:
    info = _server_info()
    ATTACH_FILE.unlink(missing_ok=True)
    if not info:
        SERVER_FILE.unlink(missing_ok=True)
        return False
    try:
        os.killpg(os.getpgid(info["pid"]), signal.SIGTERM)
    except OSError:
        try:
            os.kill(info["pid"], signal.SIGTERM)
        except OSError:
            pass
    SERVER_FILE.unlink(missing_ok=True)
    return True


# --------------------------------------------------------------------------- #
# REST helpers
# --------------------------------------------------------------------------- #
def _rest(info: dict, path: str, method: str = "GET", body: dict | None = None):
    url = f"http://localhost:{info['port']}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {info['token']}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def _require_server() -> dict:
    info = _server_info()
    if not info:
        sys.exit("No Jupyter server running. Run `nbkernel.py serve` first.")
    return info


# --------------------------------------------------------------------------- #
# attach to the kernel Cursor is using
# --------------------------------------------------------------------------- #
def attach(nb: Path) -> dict:
    info = _require_server()
    nb_name = nb.name
    sessions = _rest(info, "/api/sessions") or []

    kernel_id = None
    for s in sessions:
        path = s.get("path", "")
        if Path(path).name == nb_name and s.get("kernel"):
            kernel_id = s["kernel"]["id"]
            break

    if kernel_id is None:
        kernels = _rest(info, "/api/kernels") or []
        alive = [k for k in kernels if k.get("execution_state") != "dead"]
        if len(alive) == 1:
            kernel_id = alive[0]["id"]
        elif not alive:
            sys.exit(
                "No running kernel found on the server.\n"
                "In Cursor: open the notebook, 'Select Kernel' -> "
                "'Existing Jupyter Server...' -> paste the URL from "
                "`nbkernel.py server-info`, then pick the Python kernel. "
                "Then re-run `attach`."
            )
        else:
            listing = ", ".join(k["id"][:8] for k in alive)
            sys.exit(
                f"Multiple kernels running ({listing}) and none is bound to a "
                f"session for {nb_name}. Run a cell in Cursor so it registers a "
                "session, then re-run `attach`."
            )

    conn = find_connection_file(f"kernel-{kernel_id}.json")
    data = {"kernel_id": kernel_id, "connection_file": conn}
    ATTACH_FILE.write_text(json.dumps(data, indent=2))
    return data


def _client() -> BlockingKernelClient:
    if not ATTACH_FILE.exists():
        sys.exit("Not attached to a kernel. Run `nbkernel.py attach` first.")
    data = json.loads(ATTACH_FILE.read_text())
    kc = BlockingKernelClient()
    kc.load_connection_file(data["connection_file"])
    kc.start_channels()
    try:
        kc.wait_for_ready(timeout=10)
    except RuntimeError:
        kc.stop_channels()
        sys.exit("Attached kernel is not responding. Re-run `attach`.")
    return kc


# --------------------------------------------------------------------------- #
# execution
# --------------------------------------------------------------------------- #
def _execute(kc: BlockingKernelClient, code: str, timeout: float):
    msg_id = kc.execute(code, allow_stdin=False)
    outputs: list[dict] = []
    status = "ok"
    exec_count: int | None = None

    while True:
        try:
            msg = kc.get_iopub_msg(timeout=timeout)
        except Empty:
            status = "timeout"
            break
        if msg["parent_header"].get("msg_id") != msg_id:
            continue
        mtype = msg["header"]["msg_type"]
        content = msg["content"]

        if mtype == "status":
            if content["execution_state"] == "idle":
                break
        elif mtype == "stream":
            if outputs and outputs[-1].get("output_type") == "stream" \
                    and outputs[-1]["name"] == content["name"]:
                outputs[-1]["text"] += content["text"]
            else:
                outputs.append({
                    "output_type": "stream",
                    "name": content["name"],
                    "text": content["text"],
                })
        elif mtype == "execute_result":
            exec_count = content.get("execution_count")
            outputs.append({
                "output_type": "execute_result",
                "data": content["data"],
                "metadata": content.get("metadata", {}),
                "execution_count": exec_count,
            })
        elif mtype == "display_data":
            outputs.append({
                "output_type": "display_data",
                "data": content["data"],
                "metadata": content.get("metadata", {}),
            })
        elif mtype == "error":
            status = "error"
            outputs.append({
                "output_type": "error",
                "ename": content["ename"],
                "evalue": content["evalue"],
                "traceback": content["traceback"],
            })

    try:
        reply = kc.get_shell_msg(timeout=timeout)
        if reply["parent_header"].get("msg_id") == msg_id:
            exec_count = reply["content"].get("execution_count", exec_count)
    except Empty:
        pass

    return outputs, status, exec_count


def _print_outputs(outputs: list[dict], status: str, exec_count) -> None:
    print(f"[status={status} execution_count={exec_count}]")
    for out in outputs:
        ot = out["output_type"]
        if ot == "stream":
            sys.stdout.write(out["text"])
        elif ot in ("execute_result", "display_data"):
            data = out["data"]
            if "text/plain" in data:
                txt = data["text/plain"]
                print(txt if isinstance(txt, str) else "".join(txt))
            non_text = [k for k in data if k != "text/plain"]
            if non_text:
                print(f"[rich output: {', '.join(non_text)}]")
        elif ot == "error":
            print("\n".join(out["traceback"]))


# --------------------------------------------------------------------------- #
# notebook helpers
# --------------------------------------------------------------------------- #
def _load_nb(path: Path):
    return nbformat.read(str(path), as_version=4)


def cmd_list(path: Path) -> None:
    nb = _load_nb(path)
    for i, cell in enumerate(nb.cells):
        first = (cell.source.splitlines() or [""])[0]
        marker = "code" if cell.cell_type == "code" else cell.cell_type
        ec = getattr(cell, "execution_count", None)
        ec_s = f" [{ec}]" if ec else ""
        print(f"{i:3d} {marker:8s}{ec_s} | {first[:70]}")


def run_cell(path: Path, index: int, timeout: float, write: bool) -> None:
    nb = _load_nb(path)
    if index < 0 or index >= len(nb.cells):
        sys.exit(f"Cell index {index} out of range (0..{len(nb.cells) - 1}).")
    cell = nb.cells[index]
    if cell.cell_type != "code":
        sys.exit(f"Cell {index} is a {cell.cell_type} cell, not code.")

    kc = _client()
    try:
        outputs, status, exec_count = _execute(kc, cell.source, timeout)
    finally:
        kc.stop_channels()

    print(f"# cell {index}")
    _print_outputs(outputs, status, exec_count)

    if write:
        # Only safe when Cursor is NOT also editing the file, or it may clash
        # with Cursor's own document state. Off by default for that reason.
        cell.outputs = [nbformat.from_dict(o) for o in outputs]
        cell.execution_count = exec_count
        nbformat.write(nb, str(path))


def run_code(code: str, timeout: float) -> None:
    kc = _client()
    try:
        outputs, status, exec_count = _execute(kc, code, timeout)
    finally:
        kc.stop_channels()
    _print_outputs(outputs, status, exec_count)


def show_vars() -> None:
    code = (
        "import json as _json\n"
        "_ns = {k: type(v).__name__ for k, v in globals().items()\n"
        "       if not k.startswith('_') and k not in ('In','Out','exit','quit','get_ipython')}\n"
        "print(_json.dumps(_ns, indent=2))"
    )
    run_code(code, timeout=30)


def restart_kernel() -> None:
    info = _require_server()
    if not ATTACH_FILE.exists():
        sys.exit("Not attached. Run `attach` first.")
    kid = json.loads(ATTACH_FILE.read_text())["kernel_id"]
    _rest(info, f"/api/kernels/{kid}/restart", method="POST")
    print(f"kernel {kid[:8]} restarted (state cleared)")


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_nb(sp):
        sp.add_argument("--nb", type=Path, default=DEFAULT_NB, help="notebook path")

    sub.add_parser("serve", help="start the Jupyter server")
    sub.add_parser("server-info", help="print URL+token to paste into Cursor")
    sub.add_parser("status", help="show server + attached kernel state")
    sub.add_parser("stop", help="shut down the Jupyter server")
    sub.add_parser("vars", help="list user-defined variables in the kernel")
    sub.add_parser("restart-kernel", help="restart the shared kernel (clears state)")

    sp = sub.add_parser("attach", help="attach to the kernel Cursor is using")
    add_nb(sp)
    sp = sub.add_parser("list", help="list cells in the notebook")
    add_nb(sp)

    sp = sub.add_parser("run-cell", help="run one cell's source in the shared kernel")
    sp.add_argument("index", type=int)
    sp.add_argument("--timeout", type=float, default=120)
    sp.add_argument("--write", action="store_true",
                    help="also write outputs back to the .ipynb (may clash with Cursor)")
    add_nb(sp)

    sp = sub.add_parser("run-cells", help="run several cells' source in order")
    sp.add_argument("indices", type=int, nargs="+")
    sp.add_argument("--timeout", type=float, default=120)
    sp.add_argument("--write", action="store_true")
    add_nb(sp)

    sp = sub.add_parser("run-code", help="run arbitrary code in the shared kernel")
    sp.add_argument("code")
    sp.add_argument("--timeout", type=float, default=120)

    args = p.parse_args()

    if args.cmd == "serve":
        info = serve()
        print(f"Jupyter server running (pid={info['pid']}).")
        print(f"  URL to paste in Cursor: {info['url']}?token={info['token']}")
        print("  In Cursor: Select Kernel -> Existing Jupyter Server... -> paste URL")
        print("  -> pick the Python kernel, then run `nbkernel.py attach`.")
    elif args.cmd == "server-info":
        info = _require_server()
        print(f"{info['url']}?token={info['token']}")
    elif args.cmd == "status":
        info = _server_info()
        if info:
            print(f"server: alive (pid={info['pid']}) {info['url']}")
        else:
            print("server: not running")
        if ATTACH_FILE.exists():
            print(f"attached kernel: {json.loads(ATTACH_FILE.read_text())['kernel_id']}")
        else:
            print("attached kernel: none")
    elif args.cmd == "stop":
        print("stopped" if stop() else "no server running")
    elif args.cmd == "attach":
        data = attach(args.nb)
        print(f"attached to kernel {data['kernel_id']}")
    elif args.cmd == "list":
        cmd_list(args.nb)
    elif args.cmd == "run-cell":
        run_cell(args.nb, args.index, args.timeout, args.write)
    elif args.cmd == "run-cells":
        for idx in args.indices:
            run_cell(args.nb, idx, args.timeout, args.write)
    elif args.cmd == "run-code":
        run_code(args.code, args.timeout)
    elif args.cmd == "vars":
        show_vars()
    elif args.cmd == "restart-kernel":
        restart_kernel()


if __name__ == "__main__":
    main()
