#!/usr/bin/env bash
#
# HISTORICAL — already executed on 2026-09-01. The move it performs is done;
# the project now lives at ~/dev/Project-Beta. Kept as a record of the fix,
# not as a script to run again. Its preflight will refuse to re-run.
# PROJECT BETA — move the project out of the macOS TCC-protected Desktop.
#
# WHY: ~/Desktop is a macOS TCC (privacy) protected location. A launchd agent
# has no access and cannot even exec a script living there:
#     /bin/bash: .../run_market_open.sh: Operation not permitted
# Terminal HAS that access, which is why manual runs worked and the scheduled
# run did not. Milestone 3 requires unattended operation through market hours,
# so the tree must live somewhere a scheduler can reach it.
#
# Destination is ~/dev/Project-Beta, NOT ~/projects/Project-Beta — macOS
# filesystems are case-insensitive by default, so that would collide with the
# existing ~/projects/project-beta.
#
# REVISED 2026-09-01 (evening): this NO LONGER re-installs the launchd job.
# com.projectbeta.marketopen was retired once Q2/Q2b and the options questions
# closed. The plist is repointed and kept in-repo as a record, but nothing is
# bootstrapped. Re-installing it would put a pointless market-open run back on
# the machine every morning.
#
# Run from Terminal:  bash ~/Desktop/Project-Beta/fix_launchd_tcc.sh

set -uo pipefail

OLD="$HOME/Desktop/Project-Beta"
NEW="$HOME/dev/Project-Beta"
LABEL="com.projectbeta.marketopen"

echo "1/6 preflight"
if [ ! -d "$OLD" ]; then echo "FATAL: $OLD not found — already moved?"; exit 1; fi
if [ -e "$NEW" ]; then echo "FATAL: $NEW already exists. Move it aside first."; exit 1; fi
for f in run_market_open.sh verify_alpaca_data.py probe_options_depth.py \
         probe_options_start.py "$LABEL.plist" .env .git src tests; do
    if [ ! -e "$OLD/$f" ]; then echo "FATAL: $OLD/$f missing — aborting, nothing moved"; exit 1; fi
done
echo "     ok: scripts, plist, .env, .git, src and tests all present"

echo "2/6 confirming the launchd job stays retired"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "     (was still loaded — now unloaded)" || echo "     already unloaded"
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "     LaunchAgents copy removed; nothing will be bootstrapped"

echo "3/6 moving $OLD -> $NEW   (mv preserves dotfiles: .env, .git, .gitignore)"
mkdir -p "$HOME/dev"
mv "$OLD" "$NEW" || { echo "FATAL: move failed, nothing changed"; exit 1; }

echo "4/6 repointing paths inside the moved tree"
sed -i '' "s|$HOME/Desktop/Project-Beta|$NEW|g" "$NEW/$LABEL.plist"
sed -i '' 's|PROJECT_DIR="$HOME/Desktop/Project-Beta"|PROJECT_DIR="$HOME/dev/Project-Beta"|' "$NEW/run_market_open.sh"

fail=0
grep -q "$NEW" "$NEW/$LABEL.plist"                   || { echo "  !! plist not repointed"; fail=1; }
grep -q 'Desktop/Project-Beta' "$NEW/$LABEL.plist"   && { echo "  !! plist still has a Desktop path"; fail=1; }
grep -q 'dev/Project-Beta' "$NEW/run_market_open.sh" || { echo "  !! runner not repointed"; fail=1; }
bash -n "$NEW/run_market_open.sh"                    || { echo "  !! runner syntax broken"; fail=1; }
if [ "$fail" -ne 0 ]; then
    echo; echo "FATAL: repointing failed. The project IS at $NEW but paths are wrong."
    echo "Fix by hand: replace Desktop/Project-Beta with dev/Project-Beta in"
    echo "  $NEW/$LABEL.plist   and   $NEW/run_market_open.sh"
    exit 1
fi
echo "     ok: all internal paths now $NEW"

echo "5/6 clearing stale artifacts"
rm -f "$NEW/launchd.err.log" "$NEW/launchd.out.log" "$NEW/.git/index.lock"
echo "     launchd logs and any stale git lock removed"

echo "6/6 verifying the repo survived the move"
cd "$NEW" || exit 1
git status --porcelain >/dev/null 2>&1 && echo "     git ok — $(git log --oneline -1)" \
    || { echo "  !! git not healthy at the new path"; exit 1; }
git remote -v | head -1

cat <<'NOTE'

────────────────────────────────────────────────────────────────────
DONE. Project is now at ~/dev/Project-Beta

The launchd job stays retired — nothing was bootstrapped.

NEXT:
  1. In the Claude desktop app, add ~/dev/Project-Beta as a connected
     folder. The old Desktop grant died with the move.
  2. Tell Claude it moved, and it will write the four current docs
     (Outline Rev 11, PRD v3.0, Decision_Tracker, Upgrade_Path) into
     the repo so you can commit them for M1.
  3. Optional: commit this script and the doc updates together.

Verify by hand if you like:
    ls ~/dev/Project-Beta
    cd ~/dev/Project-Beta && git log --oneline -3
────────────────────────────────────────────────────────────────────
NOTE
