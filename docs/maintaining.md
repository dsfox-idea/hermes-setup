# Maintaining this repository

This file is for whoever updates the repository. Installing the customization is
covered in the top-level `README.md`.

## Refresh the snapshot

`scripts/snapshot.py` exports a profile's skin, TUI patch, skills, configuration
example and Honcho plugin. Use a reviewed public-only profile and a separately
reconstructed public source checkout. Do not export a mixed working profile:
filename exclusions such as `PRIVATE_SKILL_FILES` cannot establish that the
remaining source, skill text or configuration contains no private material.

```sh
python3 -I scripts/snapshot.py --profile /path/to/public-profile --source /path/to/patched-source
python3 -I scripts/snapshot.py --profile /path/to/public-profile --source /path/to/patched-source --check
```

The inventory (`snapshot-inventory.json`) lists the files the exporter owns.
Refreshing deletes only previously exported copies whose hashes still match;
edited or unmanaged files are never removed silently.

## Change the TUI patch

1. Reconstruct the currently published patch on the pinned Hermes revision in a
   scratch source checkout. A shared source clone is acceptable for local builds;
   the publication repository must have independent object storage.
2. Apply only reviewed generic changes. Preserve newer public functionality and
   exclude unrelated additions from mixed local files.
3. In `ui-tui`, prepare dependencies with `npm ci`, then run `npm run build:ink`,
   `npm run typecheck`, the relevant `vitest` files and `npm run build`. Compare
   full-suite failures with the exact public baseline in a separate checkout.
4. Export with the explicit snapshot commands above. The exporter includes new
   untracked source files and refreshes both the patch checksum and inventory;
   a plain `git diff` omits untracked tests and modules.
5. Check patch application and the overlay build against an untouched pinned
   source in disposable state before installation. Live installation is a
   separate step: `scripts/setup.py install` updates every discovered profile.
   Do not use it to verify a build while unrelated live sessions must stay intact.

## Publication history boundary

The current remote `main` is the publication baseline. When old local history has
no common ancestor with it, create an independent clone directly from that remote
and port reviewed changes as new commits. Do not fetch or merge the old history
into that clone, use a linked worktree as isolation, or force-push the old branch.
Keep working runtime paths and unrelated local edits intact. Block outgoing pushes
from retired publication copies with a local refusal hook and disabled push URL.

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
```

It needs `gh` (authenticated), `gitleaks` and `python3` on `PATH`.

| Platform | Notes |
| --- | --- |
| macOS | `brew install gh gitleaks` |
| Linux | Install `gh` and `gitleaks` from their release pages or your distribution |
| Windows | `winget install GitHub.cli Gitleaks.Gitleaks`; run `git push` from Git Bash. The hook calls `python3`, which Windows does not provide: put a `python3` wrapper on `PATH` that runs `py -3` and converts `/c/...` paths with `cygpath -w` |

Never commit credentials, OAuth grants, `.env` files, databases, memories, chats
or logs. A failed push is reported as failed; check the remote with
`git ls-remote origin refs/heads/main` before calling it published.

On machines containing private development history, require the additional
`scripts/local_publication_guard.py` gate. Its policy stays outside this tree and
checks all reachable commits, paths, file content and known private object IDs.
Include retired history roots in `deny_commits`; keep identifying strings and
fingerprints in that local policy, never in the public repository.

```sh
git config --local localPublication.required true
git config --local localPublication.guard /path/to/public-checkout/scripts/local_publication_guard.py
git config --local localPublication.policy /path/outside/the/repo/policy.json
```

## Tests

```sh
cd scripts && python3 -m unittest test_setup test_snapshot_configuration test_local_publication_guard test_tui_overlay
```
