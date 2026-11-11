"""Stop a tool call that reaches into another git repository than the session's own.

Each project has its own chat. A chat whose working directory is inside repository A must not
quietly read or write repository B: the work belongs to B's chat. Before every tool call this
module collects the paths the call names (``path``/``workdir``-style arguments, and paths written
in a terminal command or ``execute_code`` source), finds the git repository of each, and when one
lies in a different repository than the session's, asks Hermes' own approval gate first
(``{"action": "approve"}`` from ``pre_tool_call``). The owner then sees the mismatch and answers
once / for the session / always / deny; the model cannot skip the prompt.

A session without a repository (a service chat, a chat outside any project) is never checked.
Paths outside any repository (scratch, the Hermes home, system files) and repositories nested in
the session's own (submodules, vendored checkouts) count as the session's.

Command parsing is a heuristic: absolute paths, ``~/`` and ``$HOME/`` paths, ``../`` paths and the
targets of ``cd``/``pushd``/``git -C`` are found; a path assembled at run time (``D=x; cd $D``) is not.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import shlex
from typing import Callable, Iterable, Optional

log = logging.getLogger("repo-guard")

PATH_KEYS = ("path", "file_path", "filepath", "workdir", "cwd", "directory", "dir", "target", "paths")
TEXT_KEYS = ("command", "code", "script")
_STOP = r"""\s'"`;|&()<>{}\[\],"""
_BEFORE = r"""(?:(?<=^)|(?<=[\s'"`=(:]))"""
_PATTERNS = (
    re.compile(_BEFORE + r"(?:~|\$HOME|\$\{HOME\})(/[^" + _STOP + r"]*)?"),
    re.compile(_BEFORE + r"(/[^/" + _STOP + r"][^" + _STOP + r"]*)"),
    re.compile(_BEFORE + r"([A-Za-z]:[\\/][^" + _STOP + r"]*)"),
    re.compile(_BEFORE + r"(\.\.(?:[\\/][^" + _STOP + r"]*)?)"),
)
_CHDIR = re.compile(r"(?:^|[;&|(\s])(?:cd|pushd)\s+([^\s;&|)]+)|git\s+-C\s+([^\s;&|)]+)")


def _expand(raw: str, base: Path) -> Optional[Path]:
    text = raw.strip().strip("'\"")
    if not text or "://" in text or text.startswith("-"):
        return None
    home = str(Path.home())
    for prefix in ("~", "$HOME", "${HOME}"):
        if text == prefix or text.startswith(prefix + "/"):
            text = home + text[len(prefix):]
    text = os.path.expanduser(text)
    path = Path(text)
    if not path.is_absolute():
        path = base / path
    try:
        return Path(os.path.normpath(str(path)))
    except (OSError, ValueError):
        return None


def paths_in_text(text: str, base: Path) -> list:
    """Paths a shell command or script names, resolved against ``base``."""
    found = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            path = _expand(match.group(0), base)
            if path is not None:
                found.append(path)
    for match in _CHDIR.finditer(text):
        token = match.group(1) or match.group(2)
        try:
            token = shlex.split(token)[0] if token else token
        except ValueError:
            pass
        path = _expand(token or "", base)
        if path is not None:
            found.append(path)
    return found


def paths_in_call(args: dict, base: Path) -> list:
    """Every path a tool call's arguments name."""
    found = []
    workdir = None
    for key in ("workdir", "cwd"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            workdir = _expand(value, base)
    for key in PATH_KEYS:
        value = args.get(key)
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            if isinstance(item, str) and item.strip():
                path = _expand(item, base)
                if path is not None:
                    found.append(path)
    for key in TEXT_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value:
            found.extend(paths_in_text(value, workdir or base))
    return found


class Repositories:
    """Git repository roots by walking up to a ``.git`` entry (cached per directory)."""

    def __init__(self, home: Optional[Path] = None):
        self._home = (home or Path.home()).resolve()
        self._cache: dict = {}

    def root(self, path: Path) -> Optional[Path]:
        current = path
        while not current.exists() and current.parent != current:
            current = current.parent
        if current.is_file():
            current = current.parent
        try:
            current = current.resolve()
        except OSError:
            return None
        key = str(current)
        if key in self._cache:
            return self._cache[key]
        result = None
        probe = current
        while True:
            if probe == self._home:
                break
            if (probe / ".git").exists():
                result = probe
                break
            if probe.parent == probe:
                break
            probe = probe.parent
        self._cache[key] = result
        return result


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


class RepoGuard:
    def __init__(self, session_cwd: Callable[[], str], repositories: Optional[Repositories] = None,
                 allowed: Callable[[], Iterable[str]] = lambda: ()):
        self._session_cwd = session_cwd
        self._repositories = repositories or Repositories()
        self._allowed = allowed

    def _allowed_roots(self) -> list:
        roots = []
        hermes_home = os.environ.get("HERMES_HOME", "").strip()
        for raw in [hermes_home or str(Path.home() / ".hermes"), *list(self._allowed() or ())]:
            if isinstance(raw, str) and raw.strip():
                try:
                    roots.append(Path(os.path.expanduser(raw.strip())).resolve())
                except OSError:
                    pass
        return roots

    def foreign(self, tool_name: str, args: dict) -> Optional[tuple]:
        """``(session_root, foreign_root)`` when the call reaches another repository, else None."""
        raw = (self._session_cwd() or "").strip()
        if not raw or not isinstance(args, dict):
            return None
        base = Path(os.path.expanduser(raw))
        session_root = self._repositories.root(base)
        if session_root is None:
            return None
        allowed = self._allowed_roots()
        for path in paths_in_call(args, base):
            if any(_inside(path, root) for root in allowed):
                continue
            root = self._repositories.root(path)
            if root is None or _inside(root, session_root):
                continue
            if any(_inside(root, allowed_root) for allowed_root in allowed):
                continue
            return session_root, root
        return None

    def on_pre_tool_call(self, tool_name: str = "", args=None, **_) -> Optional[dict]:
        try:
            hit = self.foreign(tool_name, args if isinstance(args, dict) else {})
        except Exception:
            log.debug("repo-guard: check failed for %s", tool_name, exc_info=True)
            return None
        if hit is None:
            return None
        session_root, root = hit
        log.info("repo-guard: %s in session repo %s reaches repo %s", tool_name, session_root, root)
        return {
            "action": "approve",
            "rule_key": f"repo-guard:{session_root}->{root}",
            "message": (f"this chat works in repo {session_root.name}, but the step reaches repo {root.name} ({root}). "
                        f"If the owner declines, do not retry: tell him in one line and offer a choice: continue "
                        f"here / hand the work to a {root.name} chat (session_send project=\"{root.name}\") / "
                        f"don't do it"),
        }
