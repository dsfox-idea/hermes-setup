#!/usr/bin/env python3
"""Shared artifact policy and publication-history check."""

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


class ArtifactPolicy:
    PRIVATE_DIRECTORIES = {
        ".git", ".venv", "__pycache__", "node_modules", "secrets",
        "credentials", "sessions", "chats", "memories", "logs", "backups", "cache", "evaluation-runs",
    }
    PRIVATE_FILES = {
        "auth.json", "honcho.json", "gateway-runtime.json", "gateway.env",
        "validated-grant.json", "handoff.json", "siwc.json", ".hermes_history",
        "memory.md", "user.md", "tui-theme-boot.json", "channel_directory.json",
        "processes.json", "state.db", "projects.db", "kanban.db",
    }
    EXAMPLES = {".env.example", "config.example.json", "memory/honcho.example.json"}
    BINARY_SUFFIXES = (".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3", ".gguf", ".safetensors")

    @classmethod
    def require_public(cls, relative):
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Invalid artifact path: {relative!r}")
        if any(part.casefold() in cls.PRIVATE_DIRECTORIES for part in path.parts):
            raise ValueError(f"Private artifact directory: {relative!r}")
        normalized = path.as_posix().casefold()
        if normalized in cls.EXAMPLES:
            return
        name = path.name.casefold()
        if name in cls.PRIVATE_FILES or name.startswith(".env") or name.endswith(".env") or ".env." in name:
            raise ValueError(f"Private runtime artifact: {relative!r}")
        if name.endswith(cls.BINARY_SUFFIXES):
            raise ValueError(f"Database or model artifact: {relative!r}")
        if name.endswith(".json") and name.split(".", 1)[0] in {"auth", "credential", "credentials", "token", "tokens"}:
            raise ValueError(f"Credential artifact: {relative!r}")

    @classmethod
    def is_public(cls, relative):
        try:
            cls.require_public(relative)
        except ValueError:
            return False
        return True


class PublicationHistory:
    def __init__(self, repository):
        self.repository = repository

    def git(self, *arguments):
        return subprocess.check_output(["git", *arguments], cwd=self.repository)

    def check(self, local_revision, remote_revision):
        for revision in (local_revision, remote_revision):
            if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision):
                raise ValueError("Invalid publication revision")
        arguments = ["rev-list", local_revision]
        if set(remote_revision) != {"0"}:
            subprocess.run(["git", "merge-base", "--is-ancestor", remote_revision, local_revision], cwd=self.repository, check=True, capture_output=True)
            arguments.append("^" + remote_revision)
        revisions = self.git(*arguments).decode().splitlines()
        seen = set()
        for revision in revisions:
            paths = self.git("ls-tree", "-r", "--name-only", "-z", revision)
            for encoded in paths.split(b"\0"):
                if not encoded or encoded in seen:
                    continue
                seen.add(encoded)
                ArtifactPolicy.require_public(encoded.decode("utf-8", errors="surrogateescape"))
        print(f"Publication path policy passed: {len(revisions)} commits, {len(seen)} distinct paths")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local_revision")
    parser.add_argument("remote_revision")
    arguments = parser.parse_args()
    try:
        PublicationHistory(Path.cwd()).check(arguments.local_revision, arguments.remote_revision)
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"Refusing publication: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
