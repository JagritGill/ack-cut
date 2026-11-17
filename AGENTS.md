# Working on ack-cut

Purpose: offline review of scalar consumer offsets against explicit durable
completion events. Read [README](README.md), [architecture](docs/architecture.md)
and [related work](docs/related-work.md). No broker, hardware or job execution.

Map: `ack_cut/core.py` owns validation, state and immutable reports; `io.py` reads
bounded local JSON; `__main__.py` formats output and exits. `examples/` contains
synthetic traces; `tests/` contains definition-based oracles and CLI/guard checks;
`scripts/` contains release/example checks; `.github/workflows/ci.yml` runs CI.

Invariants: offsets are sparse record identifiers, not counts. Poll batches declare
complete coverage through explicit exclusive next positions. done means durable
application completion; commit means confirmed durable scalar state. Cuts never
reset state. All four record categories partition the known records. Unknown
coverage is never reported as a number of lost records. Preserve historical unsafe
commits even if later completion makes the final cut safe. Evidence caps must not
affect totals, gates or ordering. A lower commit can increase replay without loss.

Verification commands (run from repo root; no installation):

```sh
python3 -B -m unittest discover -s tests -v
python3.13 -B -m unittest discover -s tests -v
python3 -B scripts/check_examples.py
python3 -B scripts/check_release.py
python3 -B scripts/check_release.py --json
git diff --check
```

Use the installed interpreter's name; local verification targets Python 3.15.0 and
3.13.5. Example exit 1 is an expected finding, not a test failure; invalid traces
exit 2 without partial output. No static checker or full linter configured. Syntax
parsing is not type checking. Record actual commands and final-commit CI status;
never infer a green run from workflow configuration.

Keep owner edits and unrelated repos intact. No CodeRabbit, external reviewers,
private/employer data, credentials, network features or paid dependencies. Do not
publish, merge or change settings without applicable task authority. Use synthetic
regressions and independent definitions for semantic changes, including sparse
offsets and out-of-order completion. Keep input limits and assumptions explicit.
Do not add automatic commits, Kafka connections or pretend this verifies exactly-once
processing. Update the release inventory and docs for intentional changes.

Handoff: exact commit, dirty files, commands/results, expected nonzero exits,
unrun checks and limits. Keep machine paths, logs and coordination evidence outside
the release. See [NOTICE](NOTICE.md) and [LICENSE](LICENSE) for attribution.
