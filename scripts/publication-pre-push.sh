#!/usr/bin/env bash
set -euo pipefail
hook_directory=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
required=$(git config --local --get localPublication.required || true)
case "$required" in
  ""|false) exec "$hook_directory/publication-checks" "$@" ;;
  true) ;;
  *) printf '%s\n' 'Invalid local publication policy setting.' >&2; exit 1 ;;
esac
guard=$(git config --local --get localPublication.guard || true)
policy=$(git config --local --get localPublication.policy || true)
if [[ -z "$guard" || -z "$policy" || ! -f "$guard" || ! -f "$policy" ]]; then
  printf '%s\n' 'Required local publication policy is unavailable; refusing publication.' >&2
  exit 1
fi
repository=$(git rev-parse --show-toplevel)
exec python3 "$guard" --repository "$repository" --policy "$policy" \
  --delegate "$hook_directory/publication-checks" "$@"
