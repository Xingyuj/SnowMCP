"""Exercise transfer and recovery using disposable, unrelated Git repositories."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_commits.py"


class SyncCommitsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source repo"
        self.target = Path(self.temp.name) / "target repo"
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        for repo in (self.source, self.target):
            repo.mkdir()
            self.git(repo, "init", "-b", "main")
            self.git(repo, "config", "user.name", "Mirror Tester")
            self.git(repo, "config", "user.email", "mirror@example.test")
            self.git(repo, "config", "commit.gpgsign", "false")
            (repo / "file.txt").write_text("base\n")
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", f"Initial {repo.name}")
        self.base = self.git(self.source, "rev-parse", "HEAD").strip()
        self.original = self.git(self.target, "rev-parse", "HEAD").strip()
        (self.source / "file.txt").write_text("updated\n")
        self.git(
            self.source,
            "commit",
            "-am",
            "修复配置\n\nPreserve this body.",
            "--author",
            "Original Author <author@example.test>",
        )
        self.first = self.git(self.source, "rev-parse", "HEAD").strip()
        (self.source / "second.txt").write_text("second\n")
        self.git(self.source, "add", ".")
        self.git(self.source, "commit", "-m", "Second change")
        self.tip = self.git(self.source, "rev-parse", "HEAD").strip()

    def git(self, repo, *args):
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], env=self.env, text=True, stderr=subprocess.PIPE
        )

    def tool(self, *args, success=True):
        result = subprocess.run(
            check=False,
            args=[sys.executable, str(SCRIPT), "--target", str(self.target), *args],
            env=self.env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def sync(self, *args, success=True):
        return self.tool(
            "--source",
            str(self.source),
            "--range",
            f"{self.base}..{self.tip}",
            *args,
            success=success,
        )

    def test_preview_and_message_author_preservation(self):
        self.sync()
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD").strip(), self.original)
        self.sync("--apply")
        for src, dst in ((self.first, "HEAD~1"), (self.tip, "HEAD")):
            self.assertEqual(
                self.git(self.source, "show", "-s", "--format=%B%an%n%ae%n%aI", src),
                self.git(self.target, "show", "-s", "--format=%B%an%n%ae%n%aI", dst),
            )
        self.assertEqual((self.target / "second.txt").read_text(), "second\n")
        self.assertEqual(self.git(self.target, "remote"), "")

    def test_dirty_target_is_rejected(self):
        (self.target / "untracked.txt").write_text("keep")
        self.assertIn("uncommitted or untracked", self.sync("--apply", success=False).stderr)
        self.assertEqual((self.target / "untracked.txt").read_text(), "keep")

    def conflict(self):
        (self.target / "file.txt").write_text("target change\n")
        self.git(self.target, "commit", "-am", "Target edit")
        self.before_conflict = self.git(self.target, "rev-parse", "HEAD")
        self.sync("--apply", success=False)

    def test_conflict_continue(self):
        self.conflict()
        (self.target / "file.txt").write_text("resolved\n")
        self.git(self.target, "add", "file.txt")
        self.tool("--continue")
        self.assertEqual((self.target / "second.txt").read_text(), "second\n")
        self.assertEqual(
            self.git(self.target, "show", "-s", "--format=%B", "HEAD~1"),
            self.git(self.source, "show", "-s", "--format=%B", self.first),
        )

    def test_conflict_abort(self):
        self.conflict()
        self.tool("--abort")
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.before_conflict)
        self.assertEqual((self.target / "file.txt").read_text(), "target change\n")
        self.assertFalse((self.target / "second.txt").exists())

    def test_conflict_skip(self):
        self.conflict()
        self.tool("--skip")
        self.assertEqual((self.target / "file.txt").read_text(), "target change\n")
        self.assertTrue((self.target / "second.txt").exists())

    def test_explicit_commits(self):
        self.tool("--source", str(self.source), "--commits", self.tip, "--apply")
        self.assertEqual((self.target / "file.txt").read_text(), "base\n")
        self.assertTrue((self.target / "second.txt").exists())


if __name__ == "__main__":
    unittest.main()
