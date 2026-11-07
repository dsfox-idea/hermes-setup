# Hermes setup repository

This repository publishes a Hermes customization (skin, TUI patch, installer) in the
public GitHub repository `dsfox-idea/hermes-setup`. It is separate from the upstream Hermes checkout and
from unrelated work repositories.

## Publication policy

- The user requested automatic commit and push of completed, verified Hermes
  setup changes to this repository, without a reminder after each change.
- Honor the active session's authorization requirements. Do not treat this
  standing preference as permission to publish to another destination, make this
  repository private or public, or send conversation contents elsewhere.
- The repository is public: never commit personal rules (`SOUL.md`), memory notes,
  host names, addresses, home paths or account names. The pre-push gate refuses a
  tree that contains strings from the local `publication.denyList` file.
- Commit with the owner's global git identity, on the current branch. Do not
  create branches, rewrite history, or force-push without an explicit request.
- Do not push the upstream Hermes remote or unrelated repositories.

## Completion workflow

1. Inspect both this repository and the upstream checkout before changing files.
2. Verify the requested behavior with the real runtime and relevant tests.
3. Run `python3 scripts/snapshot.py` to refresh the configuration example, the skin,
   the upstream patch, skills and the Honcho plugin.
4. Run `python3 scripts/snapshot.py --check` and inspect the generated diff.
5. Scan staged changes and all published history with Gitleaks. Never include
   credentials, OAuth grants, `.env` files, databases, memories, chats or logs.
6. Commit the setup artifacts and push `origin main`. Read the exact remote
   commit and important changed files back before reporting publication.

Install the repository's pre-push gate with:

    git config core.hooksPath .githooks

The gate checks the destination, visibility (public needs `publication.denyList`),
branch, prohibited paths and committed content. It does not initiate a push on its own.

## Portability

- `config.example.json` is a non-secret example.
  Do not overwrite a live profile wholesale or copy another machine's login.
- `skins/dsfox-skin.yaml` is the portable palette. The complete TUI behavior also
  requires `patches/hermes-tui.patch`; install both with `scripts/setup.py install`,
  which gates the patch with `git apply --check` on the live Hermes HEAD.
- `README.md` is an impersonal install guide: no host names, user names, home
  paths, addresses or machine-specific measurements. Maintainer notes belong in
  `docs/maintaining.md`.
- Memory deployment files are a source backup with machine-specific paths and
  image checks. They are not an unattended installer for another machine.
- Keep source snapshots outside the active upstream Git history. Do not edit or
  reset unrelated source changes while refreshing the backup.
