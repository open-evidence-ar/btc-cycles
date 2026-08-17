#!/usr/bin/env python3
"""Single-command full refresh: fetch fresh data, rebuild all derived artefacts, render charts.

Usage:
    python scripts/refresh_all.py            # full refresh
    python scripts/refresh_all.py --dry-run  # show what would run, don't execute
    python scripts/refresh_all.py --no-fetch # skip network fetches, rebuild derived only

Pipeline order (each stage depends on the previous one):
  1. FETCH   — pull latest OHLCV snapshots (BTC, alts, macro)
  2. CYCLE   — rebuild BTC + alt cycle metrics from raw snapshots
  3. DERIVED — SMA floors, forward ranges, alt forward ranges, next-cycle zones
  4. HEAVY   — backtest, regime robustness, correlations, rolling corr (optional)
  5. CHARTS  — render all PNG charts (C1-C9, C-SMA)
"""

import subprocess
import sys
import time
import argparse
from pathlib import Path
from dataclasses import dataclass, field

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent


@dataclass
class Step:
    name: str
    cmd: list[str]
    label: str
    timeout: int = 300


@dataclass
class Stage:
    name: str
    steps: list[Step] = field(default_factory=list)
    parallel: bool = False


def build_pipeline(skip_fetch: bool = False) -> list[Stage]:
    """Return ordered list of stages to execute."""
    stages: list[Stage] = []

    # ── Stage 1: FETCH ───────────────────────────────────────────────────
    if not skip_fetch:
        fetch_steps = [
            Step(
                name="btc",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_data.py"),
                     "--asset", "btc", "--source", "bitstamp"],
                label="BTC (Bitstamp)",
            ),
            Step(
                name="eth",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_alts.py"),
                     "--asset", "eth", "--source", "auto"],
                label="ETH",
            ),
            Step(
                name="xrp",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_alts.py"),
                     "--asset", "xrp", "--source", "auto"],
                label="XRP",
            ),
            Step(
                name="sol",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_alts.py"),
                     "--asset", "sol", "--source", "auto"],
                label="SOL",
            ),
            Step(
                name="mstr",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_alts.py"),
                     "--asset", "mstr", "--source", "auto"],
                label="MSTR",
            ),
            Step(
                name="wgmi",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_alts.py"),
                     "--asset", "wgmi", "--source", "auto"],
                label="WGMI",
            ),
            Step(
                name="macro",
                cmd=[sys.executable, str(SCRIPTS_DIR / "fetch_macro.py")],
                label="Macro (SPX/NDX/DXY/TLT)",
            ),
        ]
        stages.append(Stage(name="FETCH", steps=fetch_steps, parallel=True))

    # ── Stage 2: CYCLE METRICS ───────────────────────────────────────────
    stages.append(Stage(
        name="CYCLE",
        steps=[
            Step(
                name="btc_metrics",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_cycle_metrics.py")],
                label="BTC cycle metrics",
            ),
            Step(
                name="alt_metrics",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_alt_cycle_metrics.py")],
                label="Alt cycle metrics",
            ),
        ],
        parallel=True,
    ))

    # ── Stage 3: DERIVED (sequential — zones depend on ranges) ───────────
    stages.append(Stage(
        name="DERIVED",
        steps=[
            Step(
                name="sma_floors",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_sma_floors.py")],
                label="SMA floors (I-18a)",
            ),
            Step(
                name="fwd_ranges",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_forward_ranges.py")],
                label="BTC forward ranges",
            ),
            Step(
                name="alt_fwd_ranges",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_alt_forward_ranges.py")],
                label="Alt forward ranges",
            ),
            Step(
                name="btc_zones",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_next_cycle_zones.py")],
                label="BTC next-cycle zones",
            ),
            Step(
                name="alt_zones",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_alt_next_cycle_zones.py")],
                label="Alt next-cycle zones",
            ),
            Step(
                name="tv_pine",
                cmd=[sys.executable, str(SCRIPTS_DIR / "export_tradingview_pine.py")],
                label="TradingView Pine exports",
            ),
            Step(
                name="align",
                cmd=[sys.executable, str(SCRIPTS_DIR / "align_to_halving.py")],
                label="Align returns to halving calendar",
            ),
            Step(
                name="cycle_status_json",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_cycle_status.py")],
                label="Cycle status JSON (for banner 'where we are today')",
            ),
        ],
        parallel=False,
    ))

    # ── Stage 4: HEAVY ANALYTICS (parallel — no cross-dependencies) ──────
    stages.append(Stage(
        name="HEAVY",
        steps=[
            Step(
                name="backtest",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_backtest.py")],
                label="Backtest by cycle",
            ),
            Step(
                name="regime",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_regime_robustness.py")],
                label="Regime robustness",
            ),
            Step(
                name="corr_phase",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_correlations_phase.py")],
                label="Phase-conditioned correlation",
            ),
            Step(
                name="rolling_corr",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_rolling_corr.py")],
                label="Rolling correlation + lead/lag",
            ),
        ],
        parallel=True,
    ))

    # ── Stage 5: CHARTS ──────────────────────────────────────────────────
    stages.append(Stage(
        name="CHARTS",
        steps=[
            Step(
                name="charts",
                cmd=[sys.executable, str(SCRIPTS_DIR / "build_charts.py")],
                label="All charts (C1-C9, C-SMA)",
            ),
        ],
        parallel=False,
    ))

    return stages


def run_step(step: Step, dry_run: bool = False) -> tuple[float, int, str]:
    """Run a single step. Returns (elapsed_seconds, returncode, stderr_tail)."""
    if dry_run:
        return (0.0, 0, "(dry run)")
    t0 = time.time()
    try:
        r = subprocess.run(
            step.cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=step.timeout,
            cwd=str(ROOT),
        )
        elapsed = time.time() - t0
        # Truncate stderr to last 500 chars for display
        stderr_tail = r.stderr[-500:] if r.stderr else ""
        return (elapsed, r.returncode, stderr_tail)
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return (elapsed, -1, "TIMEOUT")
    except Exception as e:
        elapsed = time.time() - t0
        return (elapsed, -2, str(e))


def run_stage(stage: Stage, dry_run: bool = False) -> list[tuple[Step, float, int, str]]:
    """Run all steps in a stage (parallel or serial). Returns results."""
    results = []
    if stage.parallel and not dry_run:
        # Run steps in parallel using subprocess.Popen
        procs = []
        for step in stage.steps:
            proc = subprocess.Popen(
                step.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            procs.append((step, proc, time.time()))

        for step, proc, t0 in procs:
            try:
                stdout, stderr = proc.communicate(timeout=step.timeout)
                elapsed = time.time() - t0
                results.append((step, elapsed, proc.returncode, stderr[-500:] if stderr else ""))
            except subprocess.TimeoutExpired:
                proc.kill()
                elapsed = time.time() - t0
                results.append((step, elapsed, -1, "TIMEOUT"))
    else:
        for step in stage.steps:
            elapsed, rc, stderr_tail = run_step(step, dry_run)
            results.append((step, elapsed, rc, stderr_tail))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Full pipeline refresh")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without executing")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip network fetches, rebuild derived artefacts only")
    args = parser.parse_args()

    stages = build_pipeline(skip_fetch=args.no_fetch)
    total_steps = sum(len(s.steps) for s in stages)
    total_t0 = time.time()

    print(f"\n{'='*60}")
    print(f"  REFRESH ALL — {total_steps} steps across {len(stages)} stages")
    if args.dry_run:
        print("  [DRY RUN — no commands will execute]")
    if args.no_fetch:
        print("  [--no-fetch — network fetches skipped]")
    print(f"{'='*60}\n")

    all_ok = True
    step_num = 0

    for stage in stages:
        print(f"-- {stage.name} {'-'*(56-len(stage.name))}")
        mode = "parallel" if stage.parallel else "serial"
        print(f"   ({mode})")

        results = run_stage(stage, dry_run=args.dry_run)

        for step, elapsed, rc, stderr_tail in results:
            step_num += 1
            status = "OK" if rc == 0 else f"FAIL(rc={rc})"
            if rc == -1:
                status = "TIMEOUT"
            elif rc == -2:
                status = "ERROR"
            print(f"   [{step_num:2d}/{total_steps}] {step.label:40s} {elapsed:6.1f}s  {status}")
            if rc != 0 and not args.dry_run:
                all_ok = False
                if stderr_tail:
                    # Show last few lines of stderr for debugging
                    lines = stderr_tail.strip().split('\n')
                    for line in lines[-3:]:
                        print(f"         {line}")

        print()

    total_elapsed = time.time() - total_t0
    print(f"{'='*60}")
    if args.dry_run:
        print(f"  DRY RUN complete — {total_steps} steps would execute")
    elif all_ok:
        print(f"  ALL OK — {total_steps} steps in {total_elapsed:.1f}s")
    else:
        print(f"  SOME FAILURES — check output above")
        print(f"  Elapsed: {total_elapsed:.1f}s")
    print(f"{'='*60}\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
