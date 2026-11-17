"""Explicit one-partition trace semantics, with no broker or job execution."""

from dataclasses import asdict, dataclass
import re

MAX_OFFSET = 2**63 - 1
MAX_EVENTS = 10_000
MAX_RECORDS = 10_000
MAX_SNAPSHOTS = 200
MAX_EVIDENCE = 20


class TraceError(ValueError):
    """Malformed, unsupported or internally inconsistent trace."""


@dataclass(frozen=True)
class Snapshot:
    event: int
    kind: str
    label: str | None
    committed_next: int
    observed_next: int
    safe_next: int
    settled: int
    skipped_unfinished: int
    replay_completed: int
    pending_replay: int
    skipped_offsets: tuple[int, ...]
    replay_offsets: tuple[int, ...]
    omitted_skipped: int
    omitted_replay: int
    unknown_interval: tuple[int, int] | None
    regressed: bool

    @property
    def unsafe(self) -> bool:
        return self.skipped_unfinished > 0 or self.unknown_interval is not None

    def to_dict(self) -> dict:
        return {**asdict(self), "unsafe": self.unsafe}


@dataclass(frozen=True)
class Report:
    records: int
    completed: int
    commits: int
    unsafe_commits: int
    regressed_commits: int
    cuts: int
    unsafe_cuts: int
    snapshots: tuple[Snapshot, ...]

    @property
    def gate_failed(self) -> bool:
        return any(snapshot.unsafe for snapshot in self.snapshots)

    def to_dict(self) -> dict:
        return {"schema_version": 1, "records": self.records, "completed": self.completed,
                "commits": self.commits, "unsafe_commits": self.unsafe_commits,
                "regressed_commits": self.regressed_commits, "cuts": self.cuts,
                "unsafe_cuts": self.unsafe_cuts, "gate_failed": self.gate_failed,
                "snapshots": [s.to_dict() for s in self.snapshots]}


def _shape(value: object, keys: set[str], where: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise TraceError(f"{where}: incorrect fields")
    return value


def _offset(value: object, where: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_OFFSET:
        raise TraceError(f"{where}: expected an integer offset from 0 through {MAX_OFFSET}")
    return value


def audit(trace: dict, *, evidence: int = 5) -> Report:
    """Audit supplied observations. A cut is hypothetical and never resets state.

    poll declares complete coverage from the prior observed position to next,
    with only the listed visible records. commit is a confirmed durable scalar
    offset, not a request. done asserts durable application completion.
    """
    if type(evidence) is not int or not 0 <= evidence <= MAX_EVIDENCE:
        raise TraceError(f"evidence must be an integer from 0 through {MAX_EVIDENCE}")
    _shape(trace, {"start", "events"}, "trace")
    start = _offset(trace["start"], "start")
    events = trace["events"]
    if type(events) is not list or len(events) > MAX_EVENTS:
        raise TraceError(f"events must be an array of at most {MAX_EVENTS} entries")
    observed = committed = start
    # Insertion order is offset order because every poll advances coverage.
    records: dict[int, bool] = {}
    snapshots: list[Snapshot] = []
    labels: set[str] = set()
    commit_count = cut_count = 0

    def snapshot(event: int, kind: str, label: str | None = None, regressed: bool = False) -> Snapshot:
        settled = skipped = replay = pending = 0
        skipped_offsets: list[int] = []
        replay_offsets: list[int] = []
        safe = observed
        for offset, completed in records.items():
            if not completed:
                safe = min(safe, offset)
            if offset < committed:
                if completed:
                    settled += 1
                else:
                    skipped += 1
                    if len(skipped_offsets) < evidence:
                        skipped_offsets.append(offset)
            elif completed:
                replay += 1
                if len(replay_offsets) < evidence:
                    replay_offsets.append(offset)
            else:
                pending += 1
        return Snapshot(event, kind, label, committed, observed, safe, settled, skipped,
                        replay, pending, tuple(skipped_offsets), tuple(replay_offsets),
                        skipped - len(skipped_offsets), replay - len(replay_offsets),
                        (observed, committed) if committed > observed else None, regressed)

    for index, event in enumerate(events, 1):
        where = f"event {index}"
        if type(event) is not dict or type(event.get("op")) is not str:
            raise TraceError(f"{where}: expected an operation object")
        op = event["op"]
        if op == "poll":
            _shape(event, {"op", "offsets", "next"}, where)
            end = _offset(event["next"], where)
            offsets = event["offsets"]
            if end < observed:
                raise TraceError(f"{where}: poll position moved backward")
            if type(offsets) is not list or len(records) + len(offsets) > MAX_RECORDS:
                raise TraceError(f"{where}: offsets must be an array; at most {MAX_RECORDS} total records")
            previous = observed - 1
            for offset in offsets:
                offset = _offset(offset, where)
                if not previous < offset < end:
                    raise TraceError(f"{where}: offsets must increase inside the new covered interval")
                records[offset] = False
                previous = offset
            observed = end
        elif op == "done":
            _shape(event, {"op", "offset"}, where)
            offset = _offset(event["offset"], where)
            if offset not in records or records[offset]:
                raise TraceError(f"{where}: completion must name a delivered, unfinished record")
            records[offset] = True
        elif op in ("commit", "cut"):
            if len(snapshots) >= MAX_SNAPSHOTS:
                raise TraceError(f"at most {MAX_SNAPSHOTS} commit/cut observations are supported")
            if op == "commit":
                _shape(event, {"op", "next"}, where)
                next_commit = _offset(event["next"], where)
                if next_commit < start:
                    raise TraceError(f"{where}: commit precedes the trace start")
                regressed = next_commit < committed
                committed = next_commit
                commit_count += 1
                snapshots.append(snapshot(index, "commit", regressed=regressed))
            else:
                _shape(event, {"op", "label"}, where)
                label = event["label"]
                if type(label) is not str or re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", label) is None:
                    raise TraceError(f"{where}: cut label must be 1..40 ASCII letters/digits/_.-")
                if label in labels:
                    raise TraceError(f"{where}: duplicate cut label")
                labels.add(label)
                cut_count += 1
                snapshots.append(snapshot(index, "cut", label=label))
        else:
            raise TraceError(f"{where}: unsupported operation")
    snapshots.append(snapshot(len(events), "final"))
    return Report(len(records), sum(records.values()), commit_count,
                  sum(s.unsafe for s in snapshots if s.kind == "commit"),
                  sum(s.regressed for s in snapshots), cut_count,
                  sum(s.unsafe for s in snapshots if s.kind == "cut"), tuple(snapshots))
