"""Allowlisted release, Python syntax, local Markdown links and heuristic scan."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit

INVENTORY = frozenset('''
.github/workflows/ci.yml
.gitignore
AGENTS.md
LICENSE
NOTICE.md
README.md
docs/architecture.md
docs/related-work.md
ack_cut/__init__.py
ack_cut/__main__.py
ack_cut/core.py
ack_cut/io.py
examples/early-commit.json
examples/early-commit.txt
examples/regressed.json
examples/safe-frontier.json
examples/unobserved.json
scripts/check_examples.py
scripts/check_release.py
tests/test_cli_io.py
tests/test_core.py
tests/test_release.py
'''.split())
PATTERNS = [r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?' + r'PRIVATE KEY-----',
            r'gh[pousr]_' + r'[A-Za-z0-9]{30,}', r'github_pat_' + r'[A-Za-z0-9_]{30,}',
            r'AKIA' + r'[A-Z0-9]{16}', r'/' + r'Users/[^/\s]+/', r'/' + r'home/[^/\s]+/']


def inspect(root: Path) -> dict:
    found = set()
    for directory, children, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in children + files:
            if (parent / name).is_symlink():
                raise ValueError('release tree contains a symlink')
        children[:] = [c for c in children if c not in {'.git', '__pycache__', 'out'}]
        found.update((parent / f).relative_to(root).as_posix() for f in files if not f.endswith('.pyc'))
    if found != INVENTORY:
        raise ValueError(f'inventory mismatch: missing={sorted(INVENTORY-found)}, extra={sorted(found-INVENTORY)}')
    hashes = {}
    links = syntax = 0
    for name in sorted(INVENTORY):
        path = root / name
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or mode & 0o111:
            raise ValueError(f'invalid file mode: {name}')
        raw = path.read_bytes()
        if len(raw) > 128_000:
            raise ValueError(f'unexpected large file: {name}')
        content = raw.decode('utf-8')
        if any(re.search(pattern, content) for pattern in PATTERNS):
            raise ValueError(f'secret/private-path heuristic match in {name}')
        if name.endswith('.py'):
            ast.parse(content, filename=name)
            syntax += 1
        if name.endswith('.md'):
            for target in re.findall(r'\]\(([^)]+)\)', content):
                if urlsplit(target).scheme:
                    continue
                relative = unquote(target.split('#', 1)[0])
                if relative:
                    resolved = (path.parent / relative).resolve()
                    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
                        raise ValueError(f'invalid local Markdown target in {name}')
                    links += 1
        hashes[name] = hashlib.sha256(raw).hexdigest()
    return {'files': len(hashes), 'local_links': links, 'python_syntax_files': syntax, 'sha256': hashes,
            'limits': 'Heuristic checks, not full secret/provenance safety, static typing or external link verification.'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        result = inspect(Path(__file__).resolve().parents[1])
    except (ValueError, OSError, SyntaxError) as exc:
        raise SystemExit(f'release check failed: {exc}') from None
    print(json.dumps(result, indent=2) if args.json else
          f"release checks passed: {result['files']} files, {result['local_links']} local links, "
          f"{result['python_syntax_files']} Python syntax files; heuristic scan only")


if __name__ == '__main__':
    main()
