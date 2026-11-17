import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ack_cut import TraceError, audit, load_trace
from ack_cut.io import MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trace.json"

    def test_roundtrip(self):
        data = {"start": 0, "events": []}
        self.path.write_text(json.dumps(data))
        self.assertEqual(load_trace(self.path), data)

    def test_invalid_json_encodings_and_numbers(self):
        for raw in [b'\xff', b'\xef\xbb\xbf{}', b'{', b'[]', b'{"start":0,"start":1}',
                    b'{"start":0,"\\u0073tart":1}', b'{"start":NaN}', b'{"start":Infinity}',
                    b'{"start":1.0}', b'{"start":1e0}', b'{"start":' + b'9' * 21 + b'}',
                    b'[' * 2000 + b'0' + b']' * 2000]:
            self.path.write_bytes(raw)
            with self.assertRaises(TraceError):
                load_trace(self.path)

    def test_local_file_constraints(self):
        for path in [self.path, Path(self.temp.name)]:
            with self.assertRaises(TraceError):
                load_trace(path)
        self.path.write_text('{}')
        link = Path(self.temp.name) / 'link.json'
        link.symlink_to(self.path)
        with self.assertRaises(TraceError):
            load_trace(link)
        self.path.write_bytes(b'{}' + b' ' * (MAX_BYTES - 2))
        self.assertEqual(load_trace(self.path), {})
        with self.path.open('ab') as stream:
            stream.write(b' ')
        with self.assertRaises(TraceError):
            load_trace(self.path)

    def test_schema_rejects_unselected_payload(self):
        self.path.write_text('{"start":0,"events":[],"payload":"private-example"}')
        with self.assertRaises(TraceError) as context:
            audit(load_trace(self.path))
        self.assertNotIn('private-example', str(context.exception))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-B', '-m', 'ack_cut', *args], cwd=ROOT,
                              capture_output=True, text=True, check=False)

    def test_unsafe_demo_and_historical_finding(self):
        p = self.run_cli('examples/early-commit.json', '--format', 'json')
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report['gate_failed'])
        self.assertEqual(report['unsafe_commits'], 1)
        self.assertEqual(report['snapshots'][0]['skipped_offsets'], [100, 104])
        self.assertFalse(report['snapshots'][-1]['unsafe'])

    def test_text_snapshot(self):
        p = self.run_cli('examples/early-commit.json')
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, (ROOT / 'examples/early-commit.txt').read_text())

    def test_other_examples_and_help(self):
        for fixture, expected in [('safe-frontier', 0), ('unobserved', 1), ('regressed', 0)]:
            p = self.run_cli(f'examples/{fixture}.json', '--format', 'json')
            self.assertEqual(p.returncode, expected, p.stderr)
            json.loads(p.stdout)
            self.assertEqual(p.stderr, '')
        self.assertEqual(self.run_cli('--help').returncode, 0)

    def test_hidden_evidence_still_fails(self):
        p = self.run_cli('examples/early-commit.json', '--evidence', '0', '--format', 'json')
        self.assertEqual(p.returncode, 1)
        snapshot = json.loads(p.stdout)['snapshots'][0]
        self.assertEqual(snapshot['skipped_offsets'], [])
        self.assertEqual(snapshot['omitted_skipped'], 2)

    def test_errors_no_partial_report(self):
        for args in [[], ['absent.json'], ['examples/early-commit.json', '--evidence', '-1'],
                     ['examples/early-commit.json', '--evidence', 'x'],
                     ['examples/early-commit.json', '--format', 'xml']]:
            p = self.run_cli(*args)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(p.stdout, '')
            self.assertNotIn('Traceback', p.stderr)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            path.write_text('{"start":0,"events":[{"op":"commit","next":1},{"op":"done","offset":0}]}')
            p = self.run_cli(str(path))
            self.assertEqual(p.returncode, 2)
            self.assertEqual(p.stdout, '')


if __name__ == '__main__':
    unittest.main()
