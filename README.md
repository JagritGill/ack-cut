# ack-cut

**Would a crash skip unfinished work—or replay completed work?**

`ack-cut` audits a small JSON trace of one Kafka-style partition: delivered record
offsets, durable completions, confirmed scalar commits and hypothetical crash cuts.
It reports exact known-record counts and bounded offset witnesses. It runs locally
with Python's standard library, without Kafka, a network connection or an install.

The useful trap: completing offset 105 does not mean records 100 and 104 completed.
Saving 106 can skip both after a crash. Conversely, offsets 101–103 need not be
records at all: gaps are valid, so the tool never counts every integer as work.

## Quickstart

From the repository root with an existing CPython 3.13 or 3.15:

```sh
python3 -B -m ack_cut examples/early-commit.json
```

Expected **exit 1**, with:

```text
records=3 completed=3 commits=2 unsafe_commits=1 regressed_commits=0
gate=FAIL
commit@3: committed=106 observed=106 safe=100 settled=1 skipped=2 replay=0 pending=0
  unfinished below commit: [100, 104]; omitted=0
cut@4 after-high-offset: committed=106 observed=106 safe=100 settled=1 skipped=2 replay=0 pending=0
  unfinished below commit: [100, 104]; omitted=0
commit@7: committed=106 observed=106 safe=106 settled=3 skipped=0 replay=0 pending=0
cut@8 settled: committed=106 observed=106 safe=106 settled=3 skipped=0 replay=0 pending=0
final@8: committed=106 observed=106 safe=106 settled=3 skipped=0 replay=0 pending=0
```

Later completions make the final state safe. They do not erase the earlier unsafe
commit: a crash at that point would have skipped offsets 100 and 104. Findings
describe hypothetical exposure, **not proof that real data was lost**.

```sh
python3 -B -m ack_cut examples/early-commit.json --format json
python3 -B -m ack_cut examples/early-commit.json --evidence 0 --format json
python3 -B -m ack_cut examples/safe-frontier.json
python3 -B -m ack_cut examples/safe-frontier.json --format json
python3 -B -m ack_cut examples/unobserved.json
python3 -B -m ack_cut examples/regressed.json
python3 -B -m ack_cut --help
```

The early-commit and unobserved examples exit 1. Safe-frontier, regressed and help
exit 0. Safe-frontier shows one completed replay candidate while earlier work is
pending. Regressed shows two replay candidates after a stored offset moves backward;
that alone is not unfinished-work loss. Unobserved reports `[5, 8)` as unknown
coverage, **not three missing records**. `--evidence 0` hides witnesses, not findings.

## Input contract

The complete trace is an object with exactly `start` and `events`. `start` is the
initial committed and observed next offset; history below it is outside the model.
Array order is the observation order—there are no timestamps or inferred races.

| Event | Meaning |
| --- | --- |
| `{"op":"poll","offsets":[100,104,105],"next":106}` | All visible records in the interval from the previous observed position through exclusive `next` are listed. Offsets strictly increase within that interval. Missing integers are declared non-record gaps, not unknown work. An empty batch may advance coverage. |
| `{"op":"done","offset":105}` | Application work for that delivered record durably completed. Exactly once in this trace. This is stronger than merely scheduling a handler or receiving an acknowledgment callback. |
| `{"op":"commit","next":106}` | This scalar offset became durable. It is not an issued request, failed request or callback-order guess. Lower stores are allowed down to `start`; they can increase replay. |
| `{"op":"cut","label":"after-high-offset"}` | Ask what a crash/restart from the current committed offset would expose. Hypothetical only: state is not reset, and later events continue the same assignment. Labels must be unique ASCII letters/digits/`_.-`, 1–40 characters. |

Unknown fields, booleans/floats as offsets, duplicate JSON members, missing or
duplicate completions, backward polls and out-of-order/repeated deliveries are
errors. No seeks, redelivery attempts, restart events, payloads or multiple
partitions are accepted. Supply a complete trace for one stable assignment.

Every commit and explicit cut gets a snapshot; an implicit final snapshot is
always added. Event numbers are one-based; final uses the count of supplied events
(zero for an empty trace).

| Record category | At this cut |
| --- | --- |
| settled | Completed and below the committed restart position. |
| skipped unfinished | Unfinished and below the committed position: replay would skip it. |
| replay completed | Completed at or above the committed position: eligible to replay. |
| pending replay | Unfinished at or above the committed position: still eligible. |

The four counts partition all delivered records. `safe_next` is the earliest
unfinished offset, or the explicit observed next position if everything is done.
It is the largest covered restart position that skips no known unfinished record,
not an instruction sent to a broker. Commits beyond observed coverage include an
unknown interval and fail conservatively. Evidence is sorted by offset, bounded
to 0–20 entries per skipped/replay category (default 5); omitted counts are exact.

| Exit | Meaning |
| --- | --- |
| 0 | No unfinished-record skip or unknown-forward coverage in reported snapshots. Replay may still occur. |
| 1 | At least one unsafe commit, explicit cut or final snapshot. Complete report emitted. |
| 2 | Invalid/unsupported input or arguments; no partial report. |

Historical counts count observations, not distinct records lost. Repeated unsafe
snapshots may refer to the same records. Reports expose offsets and cut labels;
they are not anonymized. No payload fields are supported.

## API and verification

```python
from ack_cut import audit

report = audit({"start": 0, "events": [
    {"op": "poll", "offsets": [0, 3], "next": 4},
    {"op": "done", "offset": 3},
    {"op": "commit", "next": 4},
]})
assert report.snapshots[0].skipped_offsets == (0,)
assert report.gate_failed
```

`load_trace(path)` reads bounded JSON; `audit(trace, evidence=5)` validates and
returns immutable report dataclasses. `Report.to_dict()` emits schema version 1.
`TraceError` means invalid input. API inputs are not mutated.

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/check_examples.py
python3 -B scripts/check_release.py
python3 -B scripts/check_release.py --json
git diff --check
```

The examples harness checks all eight CLI commands and their expected statuses.
Tests include 6,104 exhaustive cases of sparse deliveries, completion orders and
commit positions against a direct restart definition. Local verification uses
Python 3.13.5 and 3.15.0; CI is configured for 3.13/3.15 on Linux. Check the actual
run for its result. Release checks include inventory, local Markdown targets,
Python syntax and selected secret/private-path patterns; they are not a static
type check, full linter or guarantee of security/provenance. No static checker is
configured. See [AGENTS.md](AGENTS.md) for commands and handoff boundaries.

## Scope and limits

This is a conditional audit of supplied facts, not a Kafka client, broker emulator,
transaction checker or proof of exactly-once processing. It assumes complete
delivery coverage, truthful durable completion events and confirmed scalar stores.
It does not model rebalances, leader epochs, retention, compaction after the trace,
offset expiration, custom acknowledgment maps, transactional sinks or deduplication.
Those can change real recovery behavior. No crash is actually performed.

Input is bounded to 2 MiB, 10,000 events, 10,000 records and 200 commit/cut
observations plus the final snapshot. Offsets are integers from 0 through 2^63−1.
Use trusted stable local regular files; symlinks/devices are rejected, but this is
not a hostile-filesystem race defense. The bounded document is parsed in memory.

See [architecture and tradeoffs](docs/architecture.md),
[related work](docs/related-work.md) and [dependency/provenance notices](NOTICE.md).
This independently implemented, AI-assisted project uses [MIT](LICENSE) for
original files. Apache Kafka is a trademark of the Apache Software Foundation;
this project is not affiliated with or endorsed by it.
