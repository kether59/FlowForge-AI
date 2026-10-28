"""Exécution isolée (sous-processus) du code utilisateur du Code Node.

Sécurité : le code tourne dans un processus Python séparé (`-I` = mode isolé,
sans site-packages utilisateur), avec un timeout et une capture stdout. Ce n'est
PAS un vrai bac à sable de sécurité (pas de seccomp/nsjail) : en production,
exécutez ce worker dans un conteneur sans réseau, avec un utilisateur non-root,
gVisor ou Firecracker.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

RUNNER = r'''
import base64, json, sys, traceback

raw = sys.stdin.read()
data = json.loads(raw)
payload = data.get("payload")
context = data.get("context") or {}
code = base64.b64decode(data["code"]).decode("utf-8")

ns = {"payload": payload, "context": context, "json": json, "result": None}

def emit(value):
    ns["result"] = value

ns["emit"] = emit
try:
    exec(compile(code, "<code-node>", "exec"), ns)
    if ns.get("result") is None:
        for name in ("run", "main"):
            fn = ns.get(name)
            if callable(fn):
                try:
                    ns["result"] = fn(payload, context)
                except TypeError:
                    ns["result"] = fn(payload)
                break
    out = {"ok": True, "result": ns.get("result")}
except Exception:
    out = {"ok": False, "error": traceback.format_exc(limit=6)}
sys.stdout.write(json.dumps(out, default=str))
'''


async def run_user_code(code: str, payload: Any, context: dict[str, Any], timeout: float = 10.0) -> tuple[Any, str | None]:
    """Retourne (result, error)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(RUNNER)
        runner_path = fh.name
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            runner_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdin = json.dumps(
            {
                "payload": payload,
                "context": context,
                "code": base64.b64encode(code.encode()).decode(),
            },
            default=str,
        ).encode()
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None, f"Timeout du Code Node après {timeout:.0f}s."
        if proc.returncode != 0:
            return None, f"Le processus a échoué (code {proc.returncode}): {stderr.decode()[:800]}"
        try:
            data = json.loads(stdout.decode() or "{}")
        except json.JSONDecodeError:
            return None, f"Sortie non JSON: {stdout.decode()[:400]}"
        if not data.get("ok"):
            return None, data.get("error", "Erreur inconnue dans le Code Node")
        return data.get("result"), None
    finally:
        Path(runner_path).unlink(missing_ok=True)
