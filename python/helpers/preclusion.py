"""
Preclusion — a pre-execution policy guard ("light-hat" defense).

The Preclusion layer inspects an *intended* action (a file mutation or a shell
command) and decides whether it may proceed, before any side effect happens.
It is the defensive core of the RSFS (Recursive State Feedback Swarm): rather
than cleaning up after a destructive action, Preclusion precludes it.

Decisions are advisory-to-enforcing depending on how the caller wires them in.
The module itself has no side effects and no third-party dependencies, so it is
safe to import anywhere and trivial to unit-test.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Verdict(str, Enum):
    """Outcome of a Preclusion evaluation."""

    ALLOW = "allow"   # no policy concern
    WARN = "warn"     # proceed, but surface the risk to the operator
    VETO = "veto"     # must not proceed


@dataclass
class Decision:
    """Result of evaluating a single action."""

    verdict: Verdict
    action: str
    reason: str = ""
    rule: str = ""
    matched: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict is not Verdict.VETO

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.verdict.value.upper()}] {self.action}: {self.reason or 'ok'}"


# Device-node classes a block-device wipe/overwrite can target. Kept in one
# place so the dd and redirect rules stay in sync.
_DEV = r"(sd|nvme|hd|vd|disk|mmcblk|mapper|md|dm-|loop|ram|xvd|pmem)"

# Shell command patterns that are destructive enough to block outright.
# Each entry is (name, compiled regex). Kept deliberately conservative: these
# match catastrophic, rarely-intentional invocations, not everyday commands.
# Every pattern is tested against both the raw command and its canonical form
# (see _canon) so quoting and ${IFS} tricks cannot smuggle the action past.
_DESTRUCTIVE_COMMANDS: list[tuple[str, re.Pattern[str]]] = [
    # Recursive AND force, targeting the root / home — order-independent flags,
    # accepting both short (-rf/-fr) and long (--recursive/--force) spellings.
    ("recursive-root-delete", re.compile(
        r"\brm\b(?=.*(?:\s-[a-z]*r|\s--recursive))"
        r"(?=.*(?:\s-[a-z]*f|\s--force))"
        r".*\s(/|/\*|~|\$HOME)(\s|$)")),
    ("disk-wipe-dd", re.compile(r"\bdd\b.*\bof=/dev/" + _DEV)),
    ("mkfs", re.compile(r"\b(mkfs(\.\w+)?|mke2fs)\b")),
    ("fork-bomb", re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;")),
    ("overwrite-block-device", re.compile(r">\s*/dev/" + _DEV)),
    # chmod recursive on root in any flag order / mode form (digits or symbolic).
    ("chmod-recursive-root", re.compile(
        r"\bchmod\b(?=.*(?:\s-[a-z]*R|\s--recursive)).*\s(/|/\*|~|\$HOME)(\s|$)")),
    ("history-wipe", re.compile(r"\bhistory\s+-c\b|>\s*~?/\.bash_history")),
    # curl/wget piped into any interpreter, with or without a path prefix.
    ("curl-pipe-shell", re.compile(
        r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(\S*/)?"
        r"(sh|bash|zsh|dash|python[0-9.]*|perl|ruby|php|node)\b")),
]

# Commands worth a warning but not an outright block.
_SUSPECT_COMMANDS: list[tuple[str, re.Pattern[str]]] = [
    # Any force+recursive rm (non-root targets like node_modules): common and
    # usually intentional, so WARN rather than VETO — root deletes are caught
    # above as a hard VETO.
    ("force-recursive-delete", re.compile(
        r"\brm\b(?=.*(?:\s-[a-z]*r|\s--recursive))(?=.*(?:\s-[a-z]*f|\s--force))")),
    ("sudo-elevation", re.compile(r"\bsudo\b")),
    ("remote-exec-ssh", re.compile(r"\bssh\b.*\s")),
    ("ownership-change", re.compile(r"\bchown\b\s+-R")),
    ("force-push", re.compile(r"\bgit\b.*\bpush\b.*(--force|-f)\b")),
]

# Additional patterns the HARDENED policy blocks outright. These target the
# classic ways an attacker turns a foothold into persistence or exfiltration.
# Defensive recognition only — the guard refuses them, it does not perform them.
_HARDENED_BLOCKED: list[tuple[str, str]] = [
    ("reverse-shell", r"(bash|sh)\s+-i\s+.*(/dev/tcp/|>&|0>&1)"),
    ("netcat-exec", r"\bnc(at|\.traditional)?\b.*\s-[a-z]*(e|c)[a-z]*\b"),
    ("obfuscated-pipe-shell",
     r"\b(base64|xxd|uudecode|openssl)\b.*(-d|--decode|enc).*\|\s*(\S*/)?"
     r"(sh|bash|zsh|dash|python[0-9.]*|perl)\b"),
    ("python-reverse", r"python[0-9.]*\s+-c\s+.*socket.*(connect|SOCK_STREAM)"),
    # crontab -e/-l/-r OR a crontab file install (no dash).
    ("crontab-persistence", r"\bcrontab\b\s+\S"),
    ("ld-preload-inject", r"\b(LD_PRELOAD|LD_AUDIT)=\S"),
    # authorized_keys write via redirect OR tee, at any path depth.
    ("ssh-authkey-append", r"(>>?|\btee\b(\s+-a)?)\s*\S*/\.ssh/authorized_keys"),
    # iptables/ip6tables flush in any flag order, plus nft flush.
    ("iptables-flush", r"\b(ip6?tables)\b.*\s(-F|--flush)\b|\bnft\b\s+flush\b"),
]


def _canon(command: str) -> str:
    """
    Canonical form used for a second matching pass: expand the common ${IFS}
    separator tricks and strip quote characters, so `rm -rf "/"` and
    `rm${IFS}-rf${IFS}/` match the same rules as `rm -rf /`. Introduces no
    realistic false positives (ordinary commands do not rely on those forms).
    """
    c = command.replace("${IFS}", " ").replace("$IFS$9", " ").replace("$IFS", " ")
    return c.replace('"', "").replace("'", "")


@dataclass
class PreclusionPolicy:
    """
    Configuration for the guard.

    protected_paths: glob patterns. Any write/delete whose target matches is
        vetoed (the drive regions we refuse to let anything mutate).
    readonly_paths: glob patterns allowed to be read but never written.
    allow_destructive: escape hatch; when True destructive commands downgrade
        from VETO to WARN (for explicitly-authorised operators only).
    extra_blocked: additional (name, regex-string) command rules.
    """

    protected_paths: list[str] = field(default_factory=list)
    readonly_paths: list[str] = field(default_factory=list)
    allow_destructive: bool = False
    extra_blocked: list[tuple[str, str]] = field(default_factory=list)

    def _compiled_extra(self) -> list[tuple[str, re.Pattern[str]]]:
        return [(name, re.compile(rx)) for name, rx in self.extra_blocked]


class Preclusion:
    """Evaluates intended actions against a policy. Stateless between calls."""

    def __init__(self, policy: PreclusionPolicy | None = None):
        self.policy = policy or PreclusionPolicy()

    # -- filesystem actions -------------------------------------------------

    def evaluate_path(self, path: str, operation: str = "write") -> Decision:
        """
        Evaluate a filesystem mutation against the protect/readonly lists.

        operation is a label like "write", "delete", "overwrite", "chmod".
        """
        norm = _normalise(path)
        action = f"{operation} {path}"

        for pattern in self.policy.protected_paths:
            if _path_matches(norm, pattern):
                return Decision(
                    Verdict.VETO,
                    action,
                    reason=f"target is under protected region '{pattern}'",
                    rule="protected-path",
                    matched=pattern,
                )

        if operation in ("write", "delete", "overwrite", "chmod", "truncate"):
            for pattern in self.policy.readonly_paths:
                if _path_matches(norm, pattern):
                    return Decision(
                        Verdict.VETO,
                        action,
                        reason=f"'{pattern}' is read-only; {operation} refused",
                        rule="readonly-path",
                        matched=pattern,
                    )

        return Decision(Verdict.ALLOW, action, reason="no protected region matched")

    # -- shell actions ------------------------------------------------------

    def evaluate_command(self, command: str) -> Decision:
        """Evaluate a shell command string."""
        action = f"exec: {command.strip()}"
        canon = _canon(command)

        def hit(rx: re.Pattern[str]) -> bool:
            return bool(rx.search(command) or rx.search(canon))

        rules = _DESTRUCTIVE_COMMANDS + self.policy._compiled_extra()
        for name, rx in rules:
            if hit(rx):
                if self.policy.allow_destructive:
                    return Decision(
                        Verdict.WARN,
                        action,
                        reason=f"destructive pattern '{name}' permitted by allow_destructive",
                        rule=name,
                        matched=name,
                    )
                return Decision(
                    Verdict.VETO,
                    action,
                    reason=f"matches destructive pattern '{name}'",
                    rule=name,
                    matched=name,
                )

        for name, rx in _SUSPECT_COMMANDS:
            if hit(rx):
                return Decision(
                    Verdict.WARN,
                    action,
                    reason=f"elevated/remote pattern '{name}'; proceed with care",
                    rule=name,
                    matched=name,
                )

        return Decision(Verdict.ALLOW, action, reason="no risky pattern matched")

    # -- batch --------------------------------------------------------------

    def evaluate_batch(self, actions: Iterable[tuple[str, str]]) -> list[Decision]:
        """
        Evaluate a sequence of (kind, value) actions.

        kind is "cmd" for a shell command, otherwise it is treated as a
        filesystem operation label and value is the path.
        """
        results: list[Decision] = []
        for kind, value in actions:
            if kind == "cmd":
                results.append(self.evaluate_command(value))
            else:
                results.append(self.evaluate_path(value, operation=kind))
        return results


def _normalise(path: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(path))
    # Keep it lexical: we must not touch the filesystem to decide policy.
    return os.path.normpath(expanded)


def _path_matches(norm_path: str, pattern: str) -> bool:
    expanded = os.path.expanduser(os.path.expandvars(pattern))
    pat = os.path.normpath(expanded)
    if fnmatch.fnmatch(norm_path, pat):
        return True
    # A "*/name" pattern should also match an unqualified / relative name,
    # since fnmatch("name", "*/name") is False (no slash to match).
    if expanded.startswith("*/") and fnmatch.fnmatch(
        os.path.basename(norm_path), expanded[2:]
    ):
        return True
    # Treat a bare directory pattern as covering everything beneath it AND the
    # directory node itself (deleting/renaming /etc must not slip through).
    bare = pat.rstrip("/*")
    if norm_path == pat or norm_path == bare or norm_path.startswith(bare + os.sep):
        return True
    if fnmatch.fnmatch(norm_path, pat.rstrip("/") + os.sep + "*"):
        return True
    return False


def default_policy() -> PreclusionPolicy:
    """A sane out-of-the-box protect-list for an Agent Zero host."""
    return PreclusionPolicy(
        protected_paths=[
            "/etc/*",
            "/boot/*",
            "/dev/*",
            "/sys/*",
            "/proc/*",
            "~/.ssh/*",
            "~/.aws/*",
            "~/.config/gcloud/*",
            "*/.git/hooks/*",
        ],
        readonly_paths=[
            "*/.env",
            "*/secrets.json",
            "*/id_rsa",
            "*/id_ed25519",
        ],
    )


def hardened_policy() -> PreclusionPolicy:
    """
    The baked-in, always-on hardened posture for the embedded swarm.

    A strict superset of default_policy(): it protects more of the host, marks
    more credential material read-only, and blocks the extra persistence and
    exfiltration command patterns in _HARDENED_BLOCKED. This is what the
    embedded swarm ships with so a fresh install is defended by default.
    """
    base = default_policy()
    base.protected_paths += [
        "/root/*",
        "/usr/bin/*",
        "/usr/sbin/*",
        "/usr/lib/*",
        "/lib/*",
        "/var/spool/cron/*",
        "~/.docker/config.json",
        "~/.kube/config",
        "~/.gnupg/*",
        "*/.git/config",
    ]
    base.readonly_paths += [
        "*/credentials",
        "*/*.pem",
        "*/*.key",
        "*/.npmrc",
        "*/.pypirc",
        "*/.netrc",
    ]
    base.extra_blocked = list(_HARDENED_BLOCKED)
    return base
