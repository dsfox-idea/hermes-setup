"""Gateway hook: run `tui_overlay.py ensure` in the background after the gateway starts.

`hermes update` restarts the gateway, so this is the point where a new checkout HEAD
first runs. The build takes ~15 s and must not delay startup, so it is detached.
The installer writes the hermes-setup clone path into setup-repo.txt next to this file.
"""

import os
from pathlib import Path
import subprocess
import sys

HOOK_DIR = Path(__file__).resolve().parent


def handle(event_type: str, context: dict) -> None:
    log_path = HOOK_DIR / "last-run.log"
    try:
        repo = Path((HOOK_DIR / "setup-repo.txt").read_text(encoding="utf-8").strip())
    except OSError as exc:
        log_path.write_text(f"setup-repo.txt unreadable: {exc}\n", encoding="utf-8")
        return
    script = repo / "scripts" / "tui_overlay.py"
    if not script.is_file():
        log_path.write_text(f"tui_overlay.py not found under {repo}\n", encoding="utf-8")
        return
    # The hook runs inside the gateway, so Hermes itself names its checkout and home.
    import hermes_constants
    checkout = Path(hermes_constants.__file__).resolve().parent
    home = hermes_constants.get_process_hermes_home()
    command = [sys.executable, "-I", str(script), "ensure", "--checkout", str(checkout), "--hermes-home", str(home)]
    flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    with open(log_path, "w", encoding="utf-8") as log:
        subprocess.Popen(command, cwd=str(repo), stdout=log,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags,
                         start_new_session=os.name != "nt")
