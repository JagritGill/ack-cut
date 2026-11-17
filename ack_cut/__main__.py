"""Exit 0: modeled cuts safe; 1: observed risk; 2: invalid trace/arguments."""

import argparse
import json
import sys

from .core import TraceError, audit
from .io import load_trace


def render(report) -> str:
    lines = [f"records={report.records} completed={report.completed} commits={report.commits} "
             f"unsafe_commits={report.unsafe_commits} regressed_commits={report.regressed_commits}",
             "gate=FAIL" if report.gate_failed else "gate=PASS (supplied trace only)"]
    for s in report.snapshots:
        heading = f"{s.kind}@{s.event}" + (f" {s.label}" if s.label else "")
        lines.append(f"{heading}: committed={s.committed_next} observed={s.observed_next} safe={s.safe_next} "
                     f"settled={s.settled} skipped={s.skipped_unfinished} "
                     f"replay={s.replay_completed} pending={s.pending_replay}")
        if s.skipped_unfinished:
            lines.append(f"  unfinished below commit: {list(s.skipped_offsets)}; omitted={s.omitted_skipped}")
        if s.replay_completed:
            lines.append(f"  completed replay candidates: {list(s.replay_offsets)}; omitted={s.omitted_replay}")
        if s.unknown_interval:
            lines.append(f"  unobserved interval: [{s.unknown_interval[0]}, {s.unknown_interval[1]}); record count unknown")
        if s.regressed:
            lines.append("  committed position regressed; replay exposure may increase")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit scalar consumer commits at hypothetical crash cuts.")
    parser.add_argument("trace", help="stable local JSON trace; one partition and assignment")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--evidence", type=int, default=5, help="offset witnesses per category (0..20)")
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.evidence <= 20:
            raise TraceError("evidence must be an integer from 0 through 20")
        report = audit(load_trace(args.trace), evidence=args.evidence)
    except TraceError as exc:
        print(f"ack-cut: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, allow_nan=False))
    else:
        print(render(report), end="")
    return int(report.gate_failed)


if __name__ == "__main__":
    raise SystemExit(main())
