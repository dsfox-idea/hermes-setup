#!/usr/bin/env python3
"""Enforce a local publication boundary across complete reachable Git history."""
from __future__ import annotations

import json
import fnmatch
import argparse
from pathlib import Path
import re
import subprocess
import sys

from artifact_policy import ArtifactPolicy


class PublicationGuard:
    def __init__(self, repository: Path, policy_path: Path):
        self.repository = repository.resolve(strict=True)
        self.policy = json.loads(policy_path.read_text())
        names = ("deny_paths", "deny_patterns", "deny_commits", "deny_blobs")
        if (type(self.policy.get("format")) is not int or self.policy["format"] != 1
                or any(not isinstance(self.policy.get(name), list)
                       or any(not isinstance(value, str) or not value for value in self.policy[name]) for name in names)):
            raise ValueError("Invalid local publication policy")
        if not any(self.policy[name] for name in names):
            raise ValueError("Empty local publication policy")
        for name in ("deny_commits", "deny_blobs"):
            for value in self.policy[name]:
                self.identifier(value)
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.policy["deny_patterns"]]

    def git(self, *arguments):
        return subprocess.check_output(["git", *arguments], cwd=self.repository, stderr=subprocess.PIPE)

    @staticmethod
    def identifier(value):
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
            raise ValueError("A full Git object identifier is required")
        return value

    def check_text(self, data):
        text = data.decode("utf-8", errors="replace")
        if any(pattern.search(text) for pattern in self.patterns):
            raise ValueError("Local-only content is reachable from this revision")

    def check_revision(self, revision):
        self.identifier(revision)
        commits = self.git("rev-list", revision, "--").decode().splitlines()
        if set(commits).intersection(self.policy["deny_commits"]):
            raise ValueError("Local-only commit history cannot be published")
        seen = set()
        for commit in commits:
            self.check_text(self.git("show", "-s", "--format=%B", commit, "--"))
            for record in self.git("ls-tree", "-r", "-z", commit).split(b"\0"):
                if not record:
                    continue
                metadata, raw_path = record.split(b"\t", 1)
                _, kind, object_id = metadata.decode().split()
                path = raw_path.decode("utf-8", errors="surrogateescape")
                ArtifactPolicy.require_public(path)
                if any(fnmatch.fnmatchcase(path.casefold(), pattern.casefold()) for pattern in self.policy["deny_paths"]):
                    raise ValueError("Local-only artifact path cannot be published")
                self.check_text(raw_path)
                if kind == "blob" and object_id not in seen:
                    if object_id in self.policy["deny_blobs"]:
                        raise ValueError("Known local-only file content cannot be published")
                    seen.add(object_id)
                    self.check_text(self.git("cat-file", "blob", object_id))
        return {"commits_checked": len(commits), "blobs_checked": len(seen)}

    def check_updates(self, updates):
        checked = []
        for line in updates.splitlines():
            fields = line.split()
            if len(fields) != 4:
                raise ValueError("Invalid pre-push update record")
            _, local_revision, _, remote_revision = fields
            self.identifier(local_revision)
            self.identifier(remote_revision)
            if set(local_revision) != {"0"}:
                checked.append(self.check_revision(local_revision))
        return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--delegate", type=Path)
    parser.add_argument("remote", nargs="?")
    parser.add_argument("url", nargs="?")
    arguments = parser.parse_args()
    try:
        guard = PublicationGuard(arguments.repository, arguments.policy)
        if arguments.check:
            revision = guard.git("rev-parse", "HEAD").decode().strip()
            print(json.dumps(guard.check_revision(revision)))
            return 0
        updates = sys.stdin.read()
        guard.check_updates(updates)
        if arguments.delegate:
            if not arguments.remote or not arguments.url:
                raise ValueError("Missing publication destination")
            return subprocess.run([str(arguments.delegate.resolve(strict=True)), arguments.remote, arguments.url],
                                  cwd=guard.repository, input=updates.encode(), check=False).returncode
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError):
        print("Publication refused by the local-only history/content policy.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
