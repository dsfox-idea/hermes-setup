"""Load shared instruction files into an ephemeral native AIChat session."""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class SharedRules:
    def __init__(self, home, cwd):
        self.home = Path(home)
        self.cwd = Path(cwd).resolve()

    def load(self):
        soul = self.home / ".hermes/SOUL.md"
        content = soul.read_text(encoding="utf-8-sig")
        if not content.strip():
            raise ValueError("SOUL.md is empty; refusing to start without shared rules")
        sources = [(soul, content)]
        directories = [self.cwd, *self.cwd.parents]
        root = next((path for path in directories if (path / ".git").exists()), None)
        chain = list(reversed(directories[:directories.index(root) + 1])) if root else [self.cwd]
        seen = {content}
        for directory in chain:
            for name in ("AGENTS.override.md", "AGENTS.md", "agents.md"):
                path = directory / name
                if not path.exists():
                    continue
                content = path.read_text(encoding="utf-8-sig")
                if not content.strip():
                    continue
                if content not in seen:
                    sources.append((path, content))
                    seen.add(content)
                break
        return sources

    def prompt(self):
        sources = self.load()
        logging.info("Loaded %s shared instruction files", len(sources))
        return "\n\n".join("## Source: {}\n\n{}".format(path, text) for path, text in sources)


class LocalChat:
    def run(self, arguments):
        prompt = SharedRules(Path.home(), Path.cwd()).prompt()
        environment = os.environ.copy()
        model = environment["AICHAT_MODEL"]
        config_dir = Path(environment["AICHAT_CONFIG_DIR"])
        with tempfile.TemporaryDirectory(prefix=".rules-", dir=config_dir) as directory:
            session = {
                "model": model,
                "save_session": False,
                "compress_threshold": 0,
                "messages": [{"role": "system", "content": prompt}],
            }
            path = Path(directory) / "shared-rules.yaml"
            path.write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")
            path.chmod(0o600)
            environment.update({
                "AICHAT_SESSIONS_DIR": directory,
                "AICHAT_REPL_PRELUDE": "session:shared-rules",
                "AICHAT_CMD_PRELUDE": "session:shared-rules",
            })
            with subprocess.Popen(["aichat", *arguments], env=environment) as process:
                while True:
                    try:
                        status = process.wait()
                        return status if status >= 0 else 128 - status
                    except KeyboardInterrupt:
                        # The foreground child receives the same terminal signal.
                        continue


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        sys.exit(LocalChat().run(sys.argv[1:]))
    except (OSError, ValueError, KeyError) as error:
        print("local-model-chat: {}".format(error), file=sys.stderr)
        sys.exit(1)
