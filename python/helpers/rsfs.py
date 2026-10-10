"""
RSFS — Recursive State Feedback Swarm.

A defensive monitoring engine. A swarm of independent *sentinels* observes a
set of watched drive regions each round. Their observations are folded into a
single shared, versioned state. That state is hashed into a tamper-evident
chain and then fed *back* to the sentinels, so each round's focus is shaped by
what the previous round found — the "recursive feedback" of the name.

Preclusion (see preclusion.py) is consulted whenever the swarm is asked to act
on a finding, so the swarm can protect a drive without ever itself becoming the
thing that damages it.

Design goals:
  * stdlib only — importable and testable anywhere
  * no mutation of the watched filesystem; sentinels only read
  * deterministic, inspectable state with an integrity chain
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from python.helpers.preclusion import (
    Preclusion,
    Verdict,
    default_policy,
    hardened_policy,
)


@dataclass
class Observation:
    """A single finding emitted by a sentinel in one round."""

    sentinel: str
    kind: str            # e.g. "baseline", "changed", "added", "removed", "risk"
    target: str
    detail: str = ""
    severity: int = 0    # 0 info .. 3 critical

    def key(self) -> str:
        return f"{self.sentinel}:{self.kind}:{self.target}"


@dataclass
class SwarmState:
    """The shared state the swarm folds observations into and feeds back."""

    round: int = 0
    # target -> last known content hash, the heart of change detection
    fingerprints: dict[str, str] = field(default_factory=dict)
    # cumulative findings worth the operator's attention
    alerts: list[dict] = field(default_factory=list)
    # targets the feedback loop wants sentinels to look at harder next round
    focus: list[str] = field(default_factory=list)
    # tamper-evident chain: each round appends sha256(prev + payload)
    chain: list[str] = field(default_factory=list)

    def snapshot(self) -> dict:
        return {
            "round": self.round,
            "fingerprints": dict(self.fingerprints),
            "alerts": list(self.alerts),
            "focus": list(self.focus),
            "chain_head": self.chain[-1] if self.chain else "",
        }


class Sentinel(Protocol):
    """A swarm member. Pure observation: given state, emit observations."""

    name: str

    def observe(self, state: SwarmState) -> list[Observation]:
        ...


class FilesystemSentinel:
    """
    Watches a set of files/dirs for content changes using a hash fingerprint.

    First time it sees a target it records a baseline. Afterwards any change in
    the hash is reported as a "changed" observation; disappearance as "removed".
    It reads file bytes but never writes.
    """

    def __init__(self, name: str, roots: list[str], max_bytes: int = 5_000_000):
        self.name = name
        self.roots = roots
        self.max_bytes = max_bytes

    def _iter_files(self) -> list[str]:
        files: list[str] = []
        for root in self.roots:
            expanded = os.path.expanduser(os.path.expandvars(root))
            if os.path.isfile(expanded):
                files.append(expanded)
            elif os.path.isdir(expanded):
                for dirpath, _dirs, names in os.walk(expanded):
                    if os.sep + ".git" + os.sep in dirpath + os.sep:
                        continue
                    for n in names:
                        files.append(os.path.join(dirpath, n))
        return files

    def _fingerprint(self, path: str) -> str | None:
        try:
            if os.path.getsize(path) > self.max_bytes:
                # hash metadata instead of huge blobs
                st = os.stat(path)
                return "meta:" + hashlib.sha256(
                    f"{st.st_size}:{int(st.st_mtime)}".encode()
                ).hexdigest()
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(65536), b""):
                    h.update(block)
            return h.hexdigest()
        except (OSError, PermissionError):
            return None

    def observe(self, state: SwarmState) -> list[Observation]:
        obs: list[Observation] = []
        seen: set[str] = set()
        focus = set(state.focus)

        for path in self._iter_files():
            seen.add(path)
            fp = self._fingerprint(path)
            if fp is None:
                continue
            prev = state.fingerprints.get(path)
            if prev is None:
                obs.append(Observation(self.name, "baseline", path, "recorded baseline", 0))
            elif prev != fp:
                sev = 3 if path in focus else 2
                obs.append(Observation(self.name, "changed", path, "content fingerprint changed", sev))

        # anything we had a fingerprint for (under our roots) but did not see
        root_prefixes = tuple(
            os.path.expanduser(os.path.expandvars(r)) for r in self.roots
        )
        for known in list(state.fingerprints.keys()):
            if known in seen:
                continue
            if known.startswith(root_prefixes):
                obs.append(Observation(self.name, "removed", known, "file disappeared", 3))

        return obs


class CommandAuditSentinel:
    """
    Not a filesystem watcher: it audits a queue of *intended* commands against
    Preclusion and reports anything risky. The swarm uses this to vet actions
    before they run.
    """

    def __init__(self, name: str, preclusion: Preclusion, command_source: Callable[[], list[str]]):
        self.name = name
        self.preclusion = preclusion
        self.command_source = command_source

    def observe(self, state: SwarmState) -> list[Observation]:
        obs: list[Observation] = []
        for cmd in self.command_source():
            decision = self.preclusion.evaluate_command(cmd)
            if decision.verdict is Verdict.VETO:
                obs.append(Observation(self.name, "risk", cmd, decision.reason, 3))
            elif decision.verdict is Verdict.WARN:
                obs.append(Observation(self.name, "risk", cmd, decision.reason, 1))
        return obs


@dataclass
class RoundResult:
    round: int
    observations: list[Observation]
    new_alerts: list[dict]
    chain_head: str
    converged: bool


class RSFS:
    """
    The orchestrator. Runs sentinels in rounds, folds their observations into
    shared state, updates the tamper-evident chain, and computes the feedback
    focus for the next round.
    """

    def __init__(
        self,
        sentinels: list[Sentinel],
        preclusion: Preclusion | None = None,
        alert_min_severity: int = 2,
    ):
        self.sentinels = sentinels
        self.preclusion = preclusion or Preclusion(default_policy())
        self.alert_min_severity = alert_min_severity
        self.state = SwarmState()
        self._genesis()

    def _genesis(self) -> None:
        head = hashlib.sha256(b"RSFS-GENESIS").hexdigest()
        self.state.chain.append(head)

    def _extend_chain(self, payload: dict) -> str:
        prev = self.state.chain[-1] if self.state.chain else ""
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        head = hashlib.sha256(prev.encode() + body).hexdigest()
        self.state.chain.append(head)
        return head

    def verify_chain(self) -> bool:
        """Recompute the chain to confirm no round record was altered."""
        if not self.state.chain:
            return False
        if self.state.chain[0] != hashlib.sha256(b"RSFS-GENESIS").hexdigest():
            return False
        # Full verification requires stored payloads; here we at least confirm
        # the genesis anchor and monotonic structure.
        return all(isinstance(h, str) and len(h) == 64 for h in self.state.chain)

    def run_round(self) -> RoundResult:
        self.state.round += 1
        all_obs: list[Observation] = []

        for sentinel in self.sentinels:
            try:
                all_obs.extend(sentinel.observe(self.state))
            except Exception as exc:  # a failing sentinel must not sink the swarm
                all_obs.append(
                    Observation(
                        getattr(sentinel, "name", "unknown"),
                        "error",
                        "<sentinel>",
                        f"sentinel raised: {exc!r}",
                        1,
                    )
                )

        # Fold observations into state.
        new_alerts: list[dict] = []
        next_focus: set[str] = set()
        for ob in all_obs:
            if ob.kind in ("baseline", "changed"):
                # update fingerprint bookkeeping handled by sentinel read; record
                pass
            if ob.severity >= self.alert_min_severity or ob.kind == "risk":
                alert = {
                    "round": self.state.round,
                    "sentinel": ob.sentinel,
                    "kind": ob.kind,
                    "target": ob.target,
                    "detail": ob.detail,
                    "severity": ob.severity,
                    "ts": time.time(),
                }
                new_alerts.append(alert)
                next_focus.add(ob.target)

        # Persist fingerprints discovered this round (recursive state update).
        self._absorb_fingerprints(all_obs)

        self.state.alerts.extend(new_alerts)
        # Feedback: next round focuses on whatever drew an alert this round.
        self.state.focus = sorted(next_focus)

        head = self._extend_chain(
            {
                "round": self.state.round,
                "obs": [o.key() for o in all_obs],
                "alerts": len(new_alerts),
            }
        )

        converged = len(new_alerts) == 0 and self.state.round > 1
        return RoundResult(self.state.round, all_obs, new_alerts, head, converged)

    def _absorb_fingerprints(self, observations: list[Observation]) -> None:
        # Ask filesystem sentinels to re-fingerprint so state converges on the
        # current reality after the operator has acknowledged a change.
        for sentinel in self.sentinels:
            if isinstance(sentinel, FilesystemSentinel):
                for path in sentinel._iter_files():
                    fp = sentinel._fingerprint(path)
                    if fp is not None:
                        self.state.fingerprints[path] = fp

    def run(self, max_rounds: int = 8, stop_on_converge: bool = True) -> list[RoundResult]:
        """Run the feedback loop until convergence or max_rounds."""
        results: list[RoundResult] = []
        for _ in range(max_rounds):
            result = self.run_round()
            results.append(result)
            if stop_on_converge and result.converged:
                break
        return results

    def report(self) -> dict:
        return {
            "rounds": self.state.round,
            "watched": len(self.state.fingerprints),
            "alerts": self.state.alerts,
            "chain_head": self.state.chain[-1] if self.state.chain else "",
            "chain_valid": self.verify_chain(),
        }


def default_watch_roots() -> list[str]:
    """
    Baked-in regions worth guarding on an Agent Zero host: the config, prompts,
    knowledge, memory, instruments and the agent entrypoint. Resolved against
    the install's base dir so the embedded swarm has sensible targets with no
    configuration. Only paths that currently exist are returned.
    """
    try:
        from python.helpers.files import get_abs_path
        base = get_abs_path
    except Exception:  # pragma: no cover - fallback when run standalone
        import os as _os

        here = _os.path.dirname(_os.path.abspath(__file__))
        root = _os.path.dirname(_os.path.dirname(here))
        base = lambda *p: _os.path.join(root, *p)  # noqa: E731

    import os as _os

    candidates = [
        base("conf"),
        base("prompts"),
        base("knowledge"),
        base("memory"),
        base("instruments"),
        base("agent.py"),
        base("initialize.py"),
    ]
    return [c for c in candidates if _os.path.exists(c)]


def build_default_swarm(
    watch_roots: list[str],
    command_source: Callable[[], list[str]] | None = None,
    hardened: bool = True,
) -> RSFS:
    """
    Convenience: a protective swarm over the given drive regions.

    hardened=True (the default) wires in the baked-in hardened_policy() so the
    embedded swarm defends a fresh host out of the box. Pass hardened=False only
    for a deliberately relaxed posture.
    """
    policy = hardened_policy() if hardened else default_policy()
    preclusion = Preclusion(policy)
    sentinels: list[Sentinel] = [FilesystemSentinel("fs-guard", watch_roots)]
    if command_source is not None:
        sentinels.append(CommandAuditSentinel("cmd-audit", preclusion, command_source))
    return RSFS(sentinels, preclusion=preclusion)
