# Maintaining this repository

This file is for whoever updates the repository. Installing the customization is
covered in the top-level `README.md`.

## Refresh the snapshot

`scripts/snapshot.py` exports the non-secret parts of a live profile (skin, TUI
patch, skills, configuration example, Honcho plugin) into this tree. Personal
rules (`SOUL.md`), memory notes and skill references that describe one owner's
machines are never exported (`PRIVATE_SKILL_FILES` in `snapshot.py`).

```sh
python3 -I scripts/snapshot.py          # write
python3 -I scripts/snapshot.py --check  # exit 1 when the tree is stale
```

The inventory (`snapshot-inventory.json`) lists the files the exporter owns.
Refreshing deletes only previously exported copies whose hashes still match;
edited or unmanaged files are never removed silently.

## Change the TUI patch

1. Make the change in a scratch `git clone --shared` of a Hermes checkout, never in
   the checkout Hermes runs from.
2. In `ui-tui`: `npm run typecheck` and the relevant `vitest` files.
3. Export with `git diff > patches/hermes-tui.patch` and update the checksum in
   `upstream.json`.
4. Rebuild locally with `scripts/setup.py install` and open a new TUI window.

## Publish

Enable the publication gate once per clone:

```sh
git config core.hooksPath .githooks
```

The pre-push hook allows only `origin`/`main`, checks every outgoing path against
`scripts/artifact_policy.py` and runs Gitleaks over the history. While the
repository is public it also needs `publication.denyList`: a local file, kept
outside the repository, with one string per line (host names, addresses, home
paths, account names) that must not appear in the pushed tree.

```sh
git config --local publication.denyList /path/outside/the/repo/deny.txt
``` It needs `gh` (authenticated), `gitleaks` and `python3` on `PATH`.

| Platform | Notes |
| --- | --- |
| macOS | `brew install gh gitleaks` |
| Linux | Install `gh` and `gitleaks` from their release pages or your distribution |
| Windows | `winget install GitHub.cli Gitleaks.Gitleaks`; run `git push` from Git Bash. The hook calls `python3`, which Windows does not provide: put a `python3` wrapper on `PATH` that runs `py -3` and converts `/c/...` paths with `cygpath -w` |

Never commit credentials, OAuth grants, `.env` files, databases, memories, chats
or logs. A failed push is reported as failed; check the remote with
`git ls-remote origin refs/heads/main` before calling it published.

`scripts/local_publication_guard.py` is an optional extra gate driven by a local
policy file outside the repository (`localPublication.required`,
`localPublication.guard`, `localPublication.policy` in the local git config).

## Tests

```sh
cd scripts && python3 -m unittest test_setup test_snapshot_configuration test_local_publication_guard
```
