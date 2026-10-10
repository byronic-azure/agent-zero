#!/usr/bin/env python3
"""
SwarmGuard standalone server.

Serves the RSFS SwarmGuard dashboard (webui/rsfs.html) and the /rsfs_scan and
/rsfs_preclude endpoints WITHOUT booting the full Agent Zero stack. It imports
the exact same engine the in-app API handlers use (python/helpers/rsfs.py and
preclusion.py), so there is zero logic drift between this and the app.

Use it to guard a drive on any machine with Python + Flask, including through a
`claude remote-control` session. For the full Agent Zero experience, run the
normal app instead; this is the lightweight, zero-config defender.

    python scripts/swarmguard_server.py            # 127.0.0.1:50080
    HOST=0.0.0.0 PORT=8080 python scripts/swarmguard_server.py

Environment:
    HOST   bind address (default 127.0.0.1; use 0.0.0.0 to expose on the LAN)
    PORT   port (default 50080)
"""

from __future__ import annotations

import os
import sys

# make the repo importable regardless of where this is launched from
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

try:
    from flask import Flask, request, jsonify, send_file
except ImportError:
    sys.exit("SwarmGuard needs Flask:  pip install flask")

# The REAL engine — identical to what the Agent Zero handlers call.
from python.helpers.rsfs import build_default_swarm, default_watch_roots
from python.helpers.preclusion import Preclusion, hardened_policy, Verdict

_PAGE = os.path.join(_REPO, "webui", "rsfs.html")

app = Flask("swarmguard")


@app.get("/csrf_token")
def csrf():
    # standalone mode has no login; the page still asks for a token.
    return jsonify({"ok": True, "token": "standalone", "runtime_id": "swarmguard"})


@app.get("/")
@app.get("/rsfs.html")
def page():
    return send_file(_PAGE)


@app.post("/rsfs_scan")
def scan():
    inp = request.get_json(force=True, silent=True) or {}
    roots = inp.get("roots") or []
    if not roots:
        roots = default_watch_roots()
    if not roots:
        return jsonify({"success": False, "error": "no watch regions available"})
    max_rounds = max(1, min(int(inp.get("max_rounds", 4)), 16))
    cmds = inp.get("commands") or []
    cs = (lambda: list(cmds)) if cmds else None
    sw = build_default_swarm(roots, command_source=cs)
    rounds = sw.run(max_rounds=max_rounds, stop_on_converge=True)
    return jsonify({
        "success": True,
        "report": sw.report(),
        "rounds": [
            {"round": r.round, "observations": len(r.observations),
             "new_alerts": r.new_alerts, "chain_head": r.chain_head,
             "converged": r.converged}
            for r in rounds
        ],
    })


@app.post("/rsfs_preclude")
def preclude():
    inp = request.get_json(force=True, silent=True) or {}
    guard = Preclusion(hardened_policy())
    out = []
    for c in inp.get("commands", []) or []:
        d = guard.evaluate_command(c)
        out.append(_as_dict(d))
    for e in inp.get("paths", []) or []:
        if isinstance(e, dict):
            path, op = e.get("path", ""), e.get("operation", "write")
        else:
            path, op = str(e), "write"
        out.append(_as_dict(guard.evaluate_path(path, operation=op)))
    vetoed = sum(1 for r in out if r["verdict"] == Verdict.VETO.value)
    return jsonify({"success": True, "decisions": out, "vetoed": vetoed, "clear": vetoed == 0})


def _as_dict(d) -> dict:
    return {"verdict": d.verdict.value, "action": d.action,
            "reason": d.reason, "rule": d.rule, "allowed": d.allowed}


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "50080"))
    roots = default_watch_roots()
    print("=" * 60)
    print("  RSFS SwarmGuard — hardened drive defense (standalone)")
    print("=" * 60)
    print(f"  Dashboard : http://{host}:{port}/rsfs.html")
    print(f"  Guarding  : {len(roots)} baked-in region(s)")
    for r in roots:
        print(f"              · {r}")
    print("  Posture   : HARDENED   ·   defensive only (reads, never writes)")
    print("=" * 60)
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
