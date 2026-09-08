#!/usr/bin/env python3
"""Copy commits between local mirror checkouts without changing Git remotes."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


class SyncError(Exception):
    pass


def git(repo, *args, check=True, input_text=None):
    result = subprocess.run(
        check=False,
        args=["git", "-C", str(repo), *args],
        input=input_text,
        text=True,
        capture_output=True,
        env={**os.environ, "GIT_EDITOR": "true"},
    )
    if check and result.returncode:
        raise SyncError(result.stderr.strip() or result.stdout.strip())
    return result


def output(repo, *args):
    return git(repo, *args).stdout.strip()


def checkout(path):
    root = Path(output(path, "rev-parse", "--show-toplevel")).resolve()
    if output(root, "rev-parse", "--is-bare-repository") == "true":
        raise SyncError("A working checkout is required.")
    return root


def git_path(repo, name):
    path = Path(output(repo, "rev-parse", "--git-path", name))
    return path if path.is_absolute() else repo / path


def resolve(repo, ref):
    return output(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")


def run(args):
    target = checkout(args.target)
    state_path = git_path(target, "mirror-sync.json")
    if args.action:
        if not state_path.exists():
            raise SyncError("No mirror sync is in progress in this checkout.")
        state = json.loads(state_path.read_text())
        result = git(target, "cherry-pick", "--" + args.action, check=False)
        print(result.stdout, end="")
        if result.returncode:
            raise SyncError(result.stderr.strip() or "Git could not resume the operation.")
        if (
            not git_path(target, "sequencer").exists()
            and not git_path(target, "CHERRY_PICK_HEAD").exists()
        ):
            state_path.unlink()
            print(f"Sync {args.action} completed. Original HEAD: {state['original_head']}")
        return

    if not args.source or not (args.commit_range or args.commits):
        raise SyncError("Provide --source and either --range BASE..TIP or --commits SHA ... .")
    source = checkout(args.source)
    if source == target:
        raise SyncError("Source and target must be different checkouts.")
    if state_path.exists():
        raise SyncError("A previous sync exists. Use --continue, --skip, or --abort.")
    if output(target, "status", "--porcelain"):
        raise SyncError("Target has uncommitted or untracked files. Commit or stash them first.")
    for marker in (
        "CHERRY_PICK_HEAD",
        "MERGE_HEAD",
        "REVERT_HEAD",
        "sequencer",
        "rebase-merge",
        "rebase-apply",
    ):
        if git_path(target, marker).exists():
            raise SyncError(f"Target already has an active Git operation: {marker}")
    if git(target, "symbolic-ref", "--quiet", "HEAD", check=False).returncode:
        raise SyncError("Check out a target branch first; detached HEAD is not supported.")
    original_head = resolve(target, "HEAD")
    if args.commit_range:
        if args.commit_range.count("..") != 1 or "..." in args.commit_range:
            raise SyncError("Use an explicit BASE..TIP range (BASE excluded, TIP included).")
        base, tip = args.commit_range.split("..")
        if not base or not tip:
            raise SyncError("Both BASE and TIP must be explicit.")
        base, tip = resolve(source, base), resolve(source, tip)
        if git(source, "merge-base", "--is-ancestor", base, tip, check=False).returncode:
            raise SyncError("BASE must be an ancestor of TIP.")
        commits = output(
            source, "rev-list", "--reverse", "--topo-order", f"{base}..{tip}"
        ).splitlines()
    else:
        commits = [resolve(source, ref) for ref in args.commits]
    if not commits:
        raise SyncError("No commits selected.")
    if len(set(commits)) != len(commits):
        raise SyncError("Duplicate commits selected.")
    for sha in commits:
        if len(output(source, "rev-list", "--parents", "-n", "1", sha).split()) > 2:
            raise SyncError(
                f"Merge commit {sha} needs an explicit mainline; select ordinary commits instead."
            )
        if git(target, "merge-base", "--is-ancestor", sha, "HEAD", check=False).returncode == 0:
            raise SyncError(f"Commit {sha} is already in target history.")

    print(
        f"Source: {source}\nTarget: {target}\nBranch: {output(target, 'branch', '--show-current')}"
    )
    for sha in commits:
        print(output(source, "show", "-s", "--format=%h %s", sha))
    if not args.apply:
        print("Preview only. Add --apply to transfer these commits in the displayed order.")
        return

    # Import objects only: no remote, branch, tag, or FETCH_HEAD changes.
    git(
        target,
        "-c",
        "protocol.file.allow=always",
        "fetch",
        "--no-tags",
        "--no-write-fetch-head",
        "--",
        str(source),
        *commits,
    )
    state_path.write_text(
        json.dumps({"original_head": original_head, "source": str(source), "commits": commits})
    )
    result = git(
        target, "cherry-pick", "--stdin", input_text="\n".join(commits) + "\n", check=False
    )
    print(result.stdout, end="")
    if result.returncode:
        if (
            not git_path(target, "sequencer").exists()
            and not git_path(target, "CHERRY_PICK_HEAD").exists()
        ):
            state_path.unlink()
        raise SyncError(
            (result.stderr.strip() or "Cherry-pick stopped.")
            + "\nResolve conflicts, git add the resolved files, then use --continue. "
            "Use --skip for an already-applied change, or --abort to cancel the sequence."
        )
    state_path.unlink()
    print(
        f"Synced {len(commits)} commits. Messages and authors preserved; commit hashes may change. No push performed."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Local source checkout (read committed history only)")
    parser.add_argument(
        "--target", required=True, help="Local target checkout; uses its current branch"
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--range", dest="commit_range", help="BASE..TIP, oldest first; excludes BASE"
    )
    selection.add_argument("--commits", nargs="+", help="Commit refs in the exact order to apply")
    parser.add_argument(
        "--apply", action="store_true", help="Apply commits; default is preview only"
    )
    actions = parser.add_mutually_exclusive_group()
    for action in ("continue", "skip", "abort"):
        actions.add_argument("--" + action, dest="action", action="store_const", const=action)
    args = parser.parse_args()
    if args.action and (args.source or args.commit_range or args.commits or args.apply):
        parser.error("Resume actions accept only --target.")
    try:
        run(args)
    except (SyncError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
