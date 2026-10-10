#!/usr/bin/env bash
# =============================================================================
# SwarmGuard bootstrap — fresh-machine, one-paste installer.
#
# Clones (or updates) agent-zero, checks out the SwarmGuard branch, sets up a
# virtualenv with Flask, and launches the SwarmGuard dashboard. Designed for a
# clean Ubuntu/Debian box; safe to re-run.
#
#   curl -fsSL <raw-url>/scripts/bootstrap-swarmguard.sh | bash
#   # or, if you already cloned the repo:
#   bash scripts/bootstrap-swarmguard.sh
#
# Env overrides:
#   REPO_URL   git URL          (default: https://github.com/byronic-azure/agent-zero.git)
#   BRANCH     branch to use    (default: claude/remote-control-integration-6vc9e6)
#   DEST       clone directory  (default: $HOME/agent-zero)
#   HOST       bind address     (default: 127.0.0.1; use 0.0.0.0 to expose)
#   PORT       port             (default: 50080)
# =============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/byronic-azure/agent-zero.git}"
BRANCH="${BRANCH:-claude/remote-control-integration-6vc9e6}"
DEST="${DEST:-$HOME/agent-zero}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-50080}"

say() { printf '\033[36m» %s\033[0m\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# 1. prerequisites ------------------------------------------------------------
command -v git >/dev/null 2>&1 || die "git not found — install it: sudo apt-get install -y git"
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || die "python3 not found — install it: sudo apt-get install -y python3 python3-venv"

# 2. clone or update ----------------------------------------------------------
if [ -d "$DEST/.git" ]; then
  say "Updating existing checkout at $DEST"
  git -C "$DEST" fetch origin "$BRANCH"
  git -C "$DEST" checkout "$BRANCH"
  git -C "$DEST" pull --ff-only origin "$BRANCH" || say "(local changes kept; skipped fast-forward)"
elif [ -f "$(dirname "$0")/swarmguard_server.py" ]; then
  # already running from inside a checkout
  DEST="$(cd "$(dirname "$0")/.." && pwd)"
  say "Using current checkout at $DEST"
else
  say "Cloning $REPO_URL ($BRANCH) -> $DEST"
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$DEST"
fi

cd "$DEST"

# 3. virtualenv + Flask -------------------------------------------------------
if [ ! -d ".venv-swarmguard" ]; then
  say "Creating virtualenv (.venv-swarmguard)"
  "$PY" -m venv .venv-swarmguard || die "could not create venv — install python3-venv"
fi
# shellcheck disable=SC1091
source .venv-swarmguard/bin/activate
say "Installing Flask"
pip install --quiet --upgrade pip >/dev/null 2>&1 || true
pip install --quiet flask

# 4. self-check ---------------------------------------------------------------
say "Verifying the engine imports"
python - <<'PY'
import sys, os
sys.path.insert(0, os.getcwd())
from python.helpers.rsfs import default_watch_roots
from python.helpers.preclusion import Preclusion, hardened_policy, Verdict
assert Preclusion(hardened_policy()).evaluate_command("rm -rf /").verdict is Verdict.VETO
print("  engine OK · %d baked-in region(s)" % len(default_watch_roots()))
PY

# 5. launch -------------------------------------------------------------------
say "Launching SwarmGuard on http://$HOST:$PORT/rsfs.html"
echo
HOST="$HOST" PORT="$PORT" exec python scripts/swarmguard_server.py
