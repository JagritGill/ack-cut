import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_check', ROOT / 'scripts/check_release.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in checker.INVENTORY:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_release_inventory(self):
        self.assertEqual(checker.inspect(self.root)['files'], 22)

    def test_unintended_file_and_symlink(self):
        extra = self.root / 'extra.txt'
        extra.write_text('synthetic')
        with self.assertRaises(ValueError):
            checker.inspect(self.root)
        extra.unlink()
        readme = self.root / 'README.md'
        readme.unlink()
        readme.symlink_to(self.root / 'NOTICE.md')
        with self.assertRaises(ValueError):
            checker.inspect(self.root)

    def test_disclosure_and_broken_link_patterns(self):
        path = self.root / 'README.md'
        for data in ['gh' + 'p_' + 'a' * 36, '/' + 'Users/example/private.txt', '[missing](absent.md)']:
            path.write_text(data)
            with self.assertRaises(ValueError):
                checker.inspect(self.root)

    def test_bad_syntax_and_executable_bit(self):
        path = self.root / 'ack_cut/core.py'
        path.write_text('def incomplete(:\n')
        with self.assertRaises(SyntaxError):
            checker.inspect(self.root)
        path.write_text('pass\n')
        path.chmod(0o755)
        with self.assertRaises(ValueError):
            checker.inspect(self.root)


if __name__ == '__main__':
    unittest.main()
