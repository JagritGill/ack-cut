from copy import deepcopy
from itertools import combinations, permutations
import unittest

from ack_cut import TraceError, audit
from ack_cut.core import MAX_EVENTS, MAX_OFFSET, MAX_RECORDS, MAX_SNAPSHOTS


def poll(offsets, end):
    return {"op": "poll", "offsets": offsets, "next": end}


def done(offset):
    return {"op": "done", "offset": offset}


def commit(end):
    return {"op": "commit", "next": end}


class CoreTests(unittest.TestCase):
    def test_sparse_unsafe_commit_and_later_repair(self):
        events = [poll([100, 104, 105], 106), done(105), commit(106),
                  {"op": "cut", "label": "before"}, done(100), done(104), commit(106)]
        report = audit({"start": 100, "events": events})
        self.assertEqual((report.records, report.completed, report.unsafe_commits), (3, 3, 1))
        first = report.snapshots[0]
        self.assertEqual((first.skipped_offsets, first.safe_next), ((100, 104), 100))
        self.assertEqual((first.settled, first.pending_replay, first.replay_completed), (1, 0, 0))
        self.assertFalse(report.snapshots[-1].unsafe)
        self.assertTrue(report.gate_failed)  # No retroactive erasure of the unsafe store.

    def test_frontier_skips_non_record_holes(self):
        report = audit({"start": 100, "events": [poll([100, 104, 105], 110), done(100), done(105), commit(104)]})
        current = report.snapshots[-1]
        self.assertEqual((current.safe_next, current.replay_offsets, current.pending_replay), (104, (105,), 1))
        self.assertFalse(report.gate_failed)
        report = audit({"start": 100, "events": [poll([100, 104], 110), done(100), done(104), commit(110)]})
        self.assertEqual(report.snapshots[-1].safe_next, 110)

    def test_empty_poll_coverage_and_unknown_ahead(self):
        report = audit({"start": 0, "events": [poll([], 5), commit(8)]})
        current = report.snapshots[-1]
        self.assertEqual(current.unknown_interval, (5, 8))
        self.assertEqual((current.skipped_unfinished, current.safe_next), (0, 5))
        self.assertTrue(report.gate_failed)
        report = audit({"start": 0, "events": [poll([], 5), commit(5)]})
        self.assertFalse(report.gate_failed)

    def test_regression_is_replay_not_loss(self):
        report = audit({"start": 0, "events": [poll([0, 3], 4), done(0), done(3), commit(4), commit(0)]})
        self.assertEqual(report.regressed_commits, 1)
        self.assertEqual(report.snapshots[-1].replay_offsets, (0, 3))
        self.assertFalse(report.gate_failed)

    def test_cuts_do_not_restart_or_mutate_input(self):
        trace = {"start": 0, "events": [poll([0], 1), {"op": "cut", "label": "one"},
                                       done(0), {"op": "cut", "label": "two"}]}
        original = deepcopy(trace)
        r = audit(trace)
        self.assertEqual((r.cuts, r.unsafe_cuts, r.commits), (2, 0, 0))
        self.assertEqual(r.snapshots[0].pending_replay, 1)
        self.assertEqual(r.snapshots[1].replay_completed, 1)
        self.assertEqual(trace, original)

    def test_multibatch_and_large_sparse_offsets(self):
        report = audit({"start": 0, "events": [poll([0], 1), poll([], MAX_OFFSET - 2),
                                               poll([MAX_OFFSET - 2], MAX_OFFSET), done(0), commit(MAX_OFFSET - 2)]})
        self.assertEqual(report.records, 2)
        self.assertEqual(report.snapshots[-1].safe_next, MAX_OFFSET - 2)
        self.assertFalse(report.gate_failed)
        self.assertEqual(audit({"start": MAX_OFFSET, "events": []}).snapshots[-1].safe_next, MAX_OFFSET)

    def test_evidence_truncation_does_not_change_gate(self):
        trace = {"start": 0, "events": [poll(list(range(10)), 10), done(9), commit(8)]}
        full, hidden = audit(trace, evidence=20), audit(trace, evidence=0)
        self.assertEqual(hidden.snapshots[-1].skipped_offsets, ())
        self.assertEqual(hidden.snapshots[-1].omitted_skipped, 8)
        self.assertEqual(hidden.snapshots[-1].omitted_replay, 1)
        self.assertEqual(full.unsafe_commits, hidden.unsafe_commits)
        self.assertTrue(hidden.gate_failed)

    def test_invalid_schema_and_strict_integers(self):
        traces = [None, [], {"start": 0}, {"start": 0, "events": [], "extra": 1},
                  {"start": 0, "events": ()}, {"start": 0, "events": [None]},
                  {"start": 0, "events": [{"op": "unknown"}]},
                  {"start": 0, "events": [{"op": ["done"]}]},
                  {"start": 0, "events": [{"op": "poll", "offsets": [], "next": 0, "extra": 1}]}]
        for value in [-1, True, 0.0, "0", MAX_OFFSET + 1]:
            traces.append({"start": value, "events": []})
            traces.append({"start": 0, "events": [poll([value], 1)]})
            traces.append({"start": 0, "events": [commit(value)]})
        for trace in traces:
            with self.assertRaises(TraceError):
                audit(trace)
        for evidence in [True, -1, 21, 1.0, "5"]:
            with self.assertRaises(TraceError):
                audit({"start": 0, "events": []}, evidence=evidence)

    def test_inconsistent_delivery_and_completion(self):
        sequences = [[poll([0, 0], 1)], [poll([1, 0], 2)], [poll([1], 1)], [poll([-1], 1)],
                     [poll([0], 1), poll([0], 2)], [poll([], 2), poll([], 1)],
                     [poll("0", 1)], [done(0)], [poll([0], 1), done(0), done(0)]]
        for events in sequences:
            with self.subTest(events=events), self.assertRaises(TraceError):
                audit({"start": 0, "events": events})
        with self.assertRaises(TraceError):
            audit({"start": 10, "events": [commit(9)]})

    def test_label_and_resource_bounds(self):
        for label in ["", "a" * 41, "line\nbreak", "☃", None]:
            with self.assertRaises(TraceError):
                audit({"start": 0, "events": [{"op": "cut", "label": label}]})
        with self.assertRaises(TraceError):
            audit({"start": 0, "events": [{"op": "cut", "label": "x"}] * 2})
        with self.assertRaises(TraceError):
            audit({"start": 0, "events": [poll([], 0)] * (MAX_EVENTS + 1)})
        with self.assertRaises(TraceError):
            audit({"start": 0, "events": [poll(list(range(MAX_RECORDS + 1)), MAX_RECORDS + 1)]})
        with self.assertRaises(TraceError):
            audit({"start": 0, "events": [commit(0)] * (MAX_SNAPSHOTS + 1)})
        r = audit({"start": 0, "events": [poll(list(range(MAX_RECORDS)), MAX_RECORDS)]})
        self.assertEqual(r.records, MAX_RECORDS)
        self.assertEqual(len(audit({"start": 0, "events": [commit(0)] * MAX_SNAPSHOTS}).snapshots), MAX_SNAPSHOTS + 1)

    def test_empty_trace_and_unchanged_poll(self):
        r = audit({"start": 9, "events": [poll([], 9)]})
        self.assertFalse(r.gate_failed)
        self.assertEqual(r.snapshots[-1].event, 1)
        self.assertEqual(r.to_dict()["schema_version"], 1)

    def test_exhaustive_restart_definition_oracle(self):
        # Restart definition: only offsets >= the scalar commit are eligible again.
        # Enumerate every sparse subset, every ordered completion subset and commit.
        models = 0
        for size in range(6):
            for delivered in combinations(range(5), size):
                for completed_size in range(size + 1):
                    for completion_order in permutations(delivered, completed_size):
                        completed = set(completion_order)
                        for stored in range(7):
                            trace = {"start": 0, "events": [poll(list(delivered), 5),
                                      *[done(o) for o in completion_order], commit(stored)]}
                            report = audit(trace, evidence=20)
                            s = report.snapshots[-1]
                            eligible = {o for o in delivered if o >= stored}
                            unfinished = set(delivered) - completed
                            skipped = sorted(unfinished - eligible)
                            replay = sorted(completed & eligible)
                            self.assertEqual(s.skipped_offsets, tuple(skipped))
                            self.assertEqual(s.replay_offsets, tuple(replay))
                            self.assertEqual(s.settled, len(completed - eligible))
                            self.assertEqual(s.pending_replay, len(unfinished & eligible))
                            self.assertEqual(s.safe_next, min(unfinished, default=5))
                            self.assertEqual(s.unknown_interval, (5, stored) if stored > 5 else None)
                            self.assertEqual(report.gate_failed, bool(skipped) or stored > 5)
                            self.assertEqual(s.settled + s.pending_replay + s.skipped_unfinished + s.replay_completed, size)
                            models += 1
        self.assertEqual(models, 6104)


if __name__ == "__main__":
    unittest.main()
