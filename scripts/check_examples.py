"""Run documented examples with explicit expected finding exits."""

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    (['examples/early-commit.json'], 1),
    (['examples/early-commit.json', '--format', 'json'], 1),
    (['examples/early-commit.json', '--evidence', '0', '--format', 'json'], 1),
    (['examples/safe-frontier.json'], 0),
    (['examples/safe-frontier.json', '--format', 'json'], 0),
    (['examples/unobserved.json'], 1),
    (['examples/regressed.json'], 0),
    (['--help'], 0),
]


def main() -> None:
    for args, expected in CASES:
        p = subprocess.run([sys.executable, '-B', '-m', 'ack_cut', *args], cwd=ROOT,
                           text=True, capture_output=True, check=False)
        if p.returncode != expected or p.stderr:
            raise SystemExit(f'example failed: {args}, exit {p.returncode}: {p.stderr}')
        if args == ['examples/early-commit.json']:
            if p.stdout != (ROOT / 'examples/early-commit.txt').read_text():
                raise SystemExit('text snapshot mismatch')
        if '--format' in args:
            report = json.loads(p.stdout)
            if report['gate_failed'] != bool(expected):
                raise SystemExit('JSON gate mismatch')
            if report['snapshots'][-1]['settled'] != 3:
                raise SystemExit('final settled count mismatch')
    print('8 documented CLI examples passed with expected exit statuses')


if __name__ == '__main__':
    main()
