#!/usr/bin/env bash
# PROJECT BETA — market-open verification run.
#
# Runs the two remaining Week 1 data questions at the opening bell:
#   1. verify_alpaca_data.py --feed iex --stream  -> Q2/Q2b, the decisive
#      real-time latency check. Only meaningful during market hours.
#   2. probe_options_depth.py                     -> whether options history
#      exists at all, which decides the options track's scope.
#
# This runs natively on macOS, NOT in the Cowork sandbox. That is deliberate:
# the sandbox's egress proxy refuses data.alpaca.markets (403), so anything
# scheduled through it fails before it starts.

set -uo pipefail

PROJECT_DIR="$HOME/Desktop/Project-Beta"
cd "$PROJECT_DIR" || { echo "FATAL: $PROJECT_DIR not found"; exit 1; }

LOG="$PROJECT_DIR/run_market_open.log"
exec > >(tee -a "$LOG") 2>&1

echo "════════════════════════════════════════════════════════════════"
echo "PROJECT BETA market-open run — $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "════════════════════════════════════════════════════════════════"

# launchd gives a minimal PATH, so find a real python3 rather than assuming.
PY=""
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 \
                 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
                 /usr/bin/python3; do
    [ -x "$candidate" ] && { PY="$candidate"; break; }
done
[ -z "$PY" ] && { echo "FATAL: no python3 found"; exit 1; }
echo "python: $PY ($($PY -V 2>&1))"

# Credentials stay on this machine; never echoed.
if [ ! -f .env ]; then echo "FATAL: .env missing"; exit 1; fi
set -a; . ./.env; set +a
if [ -z "${APCA_API_KEY_ID:-}" ] || [ -z "${APCA_API_SECRET_KEY:-}" ]; then
    echo "FATAL: .env did not set both keys"; exit 1
fi
echo "credentials: loaded (key id ${#APCA_API_KEY_ID} chars)"

# --stream is the whole point of running at the open, and it silently skips
# itself if `websockets` is absent. Install it before that can happen.
if ! $PY -c "import websockets" 2>/dev/null; then
    echo "installing websockets..."
    $PY -m pip install --quiet websockets \
      || $PY -m pip install --quiet --user websockets \
      || $PY -m pip install --quiet --break-system-packages websockets
fi
$PY -c "import websockets; print('websockets:', websockets.__version__)" \
  || echo "WARNING: websockets unavailable — the --stream check will be SKIPPED"

echo
echo "───────────────── 1/2  live feed + streaming latency ─────────────────"
$PY verify_alpaca_data.py --feed iex --stream --out report_live.json
echo "exit: $?"

echo
echo "───────────────── 2/2  options historical depth ──────────────────────"
$PY probe_options_depth.py
echo "exit: $?"

echo
echo "Done $(date '+%H:%M:%S %Z'). Reports:"
ls -la report_live.json report_options_depth.json 2>/dev/null || echo "  (some reports missing — see above)"
