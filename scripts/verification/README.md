# Verification scripts - historical record

These answered the Week 1 data questions. **They are a record, not part of the
running system.** Every question they exist to answer is closed; results are in
the project decision log.

| Script | Answered | Result |
|---|---|---|
| `verify_alpaca_data.py` | Q1–Q4, SIP entitlement, IEX latency (Q2/Q2b) | SIP 2016-06-10 (10.2y) · IEX real-time, streaming entitled · IEX 3.16% of consolidated volume · 40/42 full RTH sessions, 0 duplicates |
| `probe_options_depth.py` | Q6 - do options bars exist? | Yes, at every monthly expiry from 2024-06-21 |
| `probe_options_start.py` | Q6b - where does options history start? | **2024-01-18** - 31 months, 0 walk-forward folds at 36/6/6 |
| `run_market_open.sh` | Orchestrated the above at the opening bell | Retired |
| `com.projectbeta.marketopen.plist` | launchd job, 06:30 local | **Retired 2026-09-01** - booted out, not installed |
| `fix_launchd_tcc.sh` | Moved the project off the TCC-protected Desktop | **Executed 2026-09-01**; will refuse to re-run |

## Two things worth keeping from this work

**macOS TCC blocks scheduled jobs in protected folders.** A launchd agent cannot
exec a script under `~/Desktop`, `~/Documents` or `~/Downloads` - it fails with
`Operation not permitted` before running a line. Terminal *has* that access, so
**testing by hand does not test the scheduled path.** M3 requires unattended
operation; see Outline §9C.

**These scripts must run natively on macOS.** The Cowork sandbox cannot reach
`data.alpaca.markets` - its egress proxy returns 403.

## Running them again

Only if a data assumption needs re-verification. Requires credentials in `.env`
at the repo root and `websockets` importable by the interpreter the runner picks:

```bash
cd ~/dev/Project-Beta
set -a; . ./.env; set +a
python scripts/verification/verify_alpaca_data.py --feed iex --stream --out report_live.json
```

`report_*.json` outputs are gitignored - they carry per-session IEX volume,
which is vendor-derived and covered by the same redistribution terms as the
bars (Outline §20.5).
