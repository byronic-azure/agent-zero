# RSFS — Recursive State Feedback Swarm

RSFS is a **defensive** drive-protection engine for Agent Zero. A swarm of
independent *sentinels* observes watched regions of the drive each round; their
findings fold into one shared, versioned state; that state is hashed into a
tamper-evident chain and fed *back* to the sentinels, so each round's attention
is shaped by what the previous round found. Paired with the **Preclusion**
guard, the swarm can watch and protect a drive without ever itself becoming the
thing that damages it.

This is defensive security only. It reads; it never mutates the watched
filesystem, and it ships no offensive/intrusion capability.

## Components

| Piece | File | Role |
|-------|------|------|
| Preclusion guard | `python/helpers/preclusion.py` | Vetoes destructive commands and writes to protected regions **before** they run. |
| RSFS engine | `python/helpers/rsfs.py` | Runs the sentinel swarm in feedback rounds; keeps the integrity chain. |
| Scan API | `python/api/rsfs_scan.py` → `POST /rsfs_scan` | Run the swarm over drive regions. |
| Preclude API | `python/api/rsfs_preclude.py` → `POST /rsfs_preclude` | Dry-run policy check on intended actions. |
| SwarmGuard UI | `webui/rsfs.html` → served at `/rsfs.html` | Deluxe dashboard: scan, alert feed, integrity chain, Preclusion console. |
| Tests | `tests/rsfs_test.py` | 24 unit tests (stdlib only). |

## SwarmGuard dashboard

Open **`/rsfs.html`** on your running Agent Zero (same origin, so it reuses the
app's login + CSRF automatically). It gives you:

* a **Swarm Scan** panel — pick watched regions, feedback rounds, optional
  commands to audit, then "Engage Swarm";
* a live **alert feed** colour-coded by severity, with the tamper-evident
  **integrity chain** rendered as `GENESIS → hash → hash → …`;
* a **Preclusion console** to dry-run any command or path against the hardened
  policy and see `ALLOW` / `WARN` / `VETO` before anything runs.

The embedded posture is **hardened by default** (`hardened_policy()`), so a
fresh install is defended out of the box.

## How the feedback loop works

1. **Observe** — each sentinel reads its targets and emits observations
   (`baseline`, `changed`, `added`, `removed`, `risk`).
2. **Fold** — observations above a severity threshold become alerts and set the
   `focus` list.
3. **Chain** — each round appends `sha256(prev_head + round_payload)`, making
   any after-the-fact edit of a round record detectable (`verify_chain()`).
4. **Feed back** — next round, targets in `focus` are scored at higher severity,
   so a region that changed once gets watched harder.
5. **Converge** — when a round produces no new alerts, the loop stops.

Sentinels are pluggable (`Sentinel` protocol). Shipped:
`FilesystemSentinel` (content-hash change detection) and
`CommandAuditSentinel` (vets queued commands through Preclusion).

## Preclusion policy

`default_policy()` protects `/etc`, `/boot`, `/dev`, `/sys`, `/proc`,
`~/.ssh`, `~/.aws`, gcloud config and git hooks, and marks `.env`, `secrets.json`
and private keys read-only. Destructive command patterns (`rm -rf /`, `dd` to a
block device, `mkfs`, fork bombs, `curl … | sudo bash`, history wipes, …) are
**vetoed**; `sudo`, remote `ssh` and `git push --force` get a **warn**.
Set `allow_destructive=True` to downgrade vetoes to warnings for an explicitly
authorised operator.

**Bypass-hardened.** Every command rule is matched against both the raw string
and a canonical form (`_canon()` expands `${IFS}` and strips quotes), and the
flag matchers are order-independent and accept long options, so evasions like
`rm -rf "/"`, `rm --recursive --force /`, `rm${IFS}-rf${IFS}/`,
`dd … of="/dev/sda"`, `curl … | /bin/bash`, `crontab /tmp/cron`,
`tee -a ~/.ssh/authorized_keys` and `LD_AUDIT=…` are all caught. The path
matcher also covers unqualified/relative protected names and the protected
directory node itself. These are regression-tested in `tests/rsfs_test.py`.

## API examples

```bash
# Scan two drive regions and audit a queued command
curl -sX POST localhost:50001/rsfs_scan -H 'Content-Type: application/json' \
  -d '{"roots":["/home/user/agent-zero/conf","/home/user/agent-zero/prompts"],
       "max_rounds":4,"commands":["rm -rf /"]}'

# Dry-run policy check — nothing is executed
curl -sX POST localhost:50001/rsfs_preclude -H 'Content-Type: application/json' \
  -d '{"commands":["rm -rf /","ls -la"],
       "paths":[{"path":"/etc/hosts","operation":"write"}]}'
```

## Using it via Claude Remote Control

This cloud session cannot reach your local drive. To let the swarm protect a
folder on **your** machine, run `claude remote-control` in a terminal in that
folder (or use the Claude Desktop app); that session shows up in the Claude Code
app and can call the same engine against your real paths.

## Library use

```python
from python.helpers.rsfs import build_default_swarm

swarm = build_default_swarm(["/path/to/protect"])
swarm.run(max_rounds=4)          # loops until quiet
print(swarm.report())            # alerts + chain_head + chain_valid
```
