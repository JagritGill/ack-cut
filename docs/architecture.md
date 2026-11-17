# Model and implementation

The audit handles one partition and one uninterrupted assignment. Let `P` be the
observed next position, `C` the confirmed committed next position, `R` the delivered
offset set and `D` the durably completed subset. Initially `P=C=start`, with empty
sets. Everything below start is deliberately outside the model.

- Poll advances P and declares exactly which visible offsets occupy the covered
  interval. It may declare gaps or an entirely empty interval. No arithmetic
  enumeration of offsets is used.
- Done adds a delivered unfinished offset to D. A failed attempt is represented
  by absence of done, not by a completion that might later be revoked.
- Commit replaces C, even if it regresses, and records a snapshot immediately.
  Commit request/callback order is not interpreted; inputs must describe actual
  durable-store order.
- Cut records a snapshot without mutating state. It is not a restart/redelivery
  operation. The final snapshot is also an observation only.

At restart, known records with offset >= C are eligible again. Splitting that
eligibility by membership in D produces the four categories in [README](../README.md).
Any unfinished record below C is a conditional skip risk. C > P also fails because
the interval [P,C) lacks supplied coverage; its record population is unknown.
The safe frontier is min(R−D) if unfinished records exist, otherwise P.

This frontier is an established processing concept, not a new algorithm. Sparse
offsets matter: after processing records at 100 and 104, a covered next position
of 110 permits the frontier to be 110, not merely 105 and not a search for 105–109.
Reference semantics and similar implementations are credited in
[related work](related-work.md).

## Implementation choices

`core.py` validates exact object shapes and uses an insertion-ordered dictionary
from delivered offset to completion state. Strictly increasing poll coverage
makes insertion order the offset order. Done lookup is direct. Snapshots scan
the known records once, count all four categories and keep only bounded witnesses.
Snapshots and reports are frozen dataclasses containing tuples.

This intentionally favors a compact, reviewable implementation over a streaming
index or live consumer implementation. With E events, R records and S snapshots,
expected work is O(E + R*S) and retained state O(R + S*W), where W is the bounded
witness count. Trace and decoded JSON storage are additional. No performance or
memory benchmark claim is made. Max R=10,000 and explicit S<=200; final adds one.
There is no range iteration, so huge offset gaps do not consume range-sized work.

`io.py` reads at most 2 MiB + 1 bytes, checks regular-file status and decodes UTF-8
JSON. Duplicate-member callbacks reject aliases such as escaped equivalent keys.
Only integer numeric tokens are accepted, capped at 20 characters before integer
conversion; semantic range is checked in core. The decoder allocates the bounded
tree before schema validation, and recursion errors are rejected. Schema-valid
input has shallow fixed structure; arbitrary nested data is not accepted.

The CLI renders only after audit returns. If a late event is invalid, there is
no partial stdout report. Unknown fields are errors rather than ignored data.
Validation errors avoid echoing supplied values; argparse may echo command-line
arguments. Cut labels and offset witnesses are intentionally public in the report.

## Gates, history and boundaries

Gate failure is any unsafe snapshot, including earlier commits. Once an unsafe
commit occurred, later completion cannot erase its historical crash window. A
regressing commit by itself is a replay observation, not a skip-risk failure.
All snapshots are retained up to the explicit bound; evidence truncation never
hides a failure or changes a count.

The audit does not verify the truth/completeness of a trace. It does not model
consumer restarts, seek, rebalances, partitions as a group, leader epoch changes,
compaction after delivery, retention, transactions, acknowledgment metadata or
idempotent sinks. Those limitations are material: replay eligibility is not a
promise a real side effect happens twice, and a skip finding is not proof of loss.
The ordinary scalar model is different from Parallel Consumer's recovery offset
map, as [NOTICE](../NOTICE.md) and the research note explain.

The file reader assumes trusted, stable input paths. Its check/open sequence is
not designed to defeat malicious concurrent replacements. It does not execute
trace contents, write input files, connect to Kafka or trigger real crashes.

## Verification approach

Tests enumerate all delivered subsets of offsets 0..4, all ordered subsets of
completed records and commit positions 0..6: 6,104 models. A direct restart-set
definition checks skipped/replay evidence, all four counts, frontier and unknown
coverage independently of snapshot frequency/counter code. Focused tests cover
historical findings, regressions, multiple polls, huge gaps, bounds, malformed
input and actual CLI behavior. Release guard tests use synthetic temporary copies.

Runtime uses only the standard library. There is no static type-checker/linter
configuration; syntax validation is explicitly narrower. See [AGENTS](../AGENTS.md)
for contributor obligations and [README](../README.md) for reproducible commands.
