#!/usr/bin/env python3
"""Explicit, single-profile installation of optional local response review."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


class ReviewInstaller:
    def __init__(self, repository, checkout, home, run_cli=subprocess.run):
        self.repository = Path(repository).resolve()
        self.checkout = Path(checkout).resolve()
        self.home = Path(home).resolve()
        self.run_cli = run_cli
        self.patch = self.repository / 'patches/response-review-host.patch'

    def git_check(self, reverse=False):
        command = ['git', '-C', str(self.checkout), 'apply', '--check']
        if reverse:
            command.append('--reverse')
        return subprocess.run([*command, str(self.patch)], capture_output=True, text=True, timeout=15).returncode == 0

    def sources(self):
        package = self.repository / 'plugins/heretic-reviewer'
        if not all((package / name).is_file() for name in ('plugin.yaml', '__init__.py')):
            raise ValueError('Required plugin manifest or entry point is missing')
        result = []
        for source in sorted(package.rglob('*')):
            if '__pycache__' in source.parts:
                continue
            if source.is_symlink():
                raise ValueError('Linked plugin sources are not accepted')
            if source.is_file() and source.suffix in ('.py', '.yaml', '.md'):
                result.append(source)
        result.append(self.repository / 'skills/autonomous-ai-agents/heretic/scripts/request.py')
        if not result or not all(path.is_file() for path in result):
            raise ValueError('Required reviewer package files are missing')
        return result

    def destination(self, source):
        target = self.home / source.relative_to(self.repository)
        current = target
        while current != self.home:
            if current.is_symlink():
                raise ValueError('Linked profile destination is not accepted')
            current = current.parent
        return target

    def check(self):
        expected = json.loads((self.repository / 'upstream.json').read_text())['response_review']['patch_sha256']
        if hashlib.sha256(self.patch.read_bytes()).hexdigest() != expected:
            raise ValueError('Response-review host patch checksum mismatch')
        matches = all(self.destination(source).is_file() and self.destination(source).read_bytes() == source.read_bytes()
                      for source in self.sources())
        return {'host_patch_present': self.git_check(reverse=True), 'package_files_match': matches,
                'model_interpreter_present': (self.home / 'local-models/venv/bin/python').is_file(),
                'model_directory_present': (self.home / 'local-models/models/qwen36-35b-heretic').is_dir(),
                'model_execution_verified': False}

    def cli(self, *arguments):
        environment = dict(os.environ, HERMES_HOME=str(self.home), HERMES_DISABLE_LAZY_INSTALLS='1')
        for key in ('HERMES_SESSION_ID', 'HERMES_TUI_ACTIVE_SESSION_FILE', 'HERMES_TUI_RESUME'):
            environment.pop(key, None)
        return self.run_cli(['hermes', 'plugins', *arguments], env=environment,
                            capture_output=True, text=True, check=True, timeout=30)

    def install(self, apply_host_patch=False, replace=False):
        state = self.check()
        files = [(source, self.destination(source)) for source in self.sources()]
        conflicts = [target for source, target in files
                     if target.exists() and (not target.is_file() or target.read_bytes() != source.read_bytes())]
        if conflicts and not replace:
            raise FileExistsError('Existing reviewer files differ; inspect them before using --replace')
        if any(not target.is_file() for target in conflicts):
            raise ValueError('A reviewer file destination is not a regular file')
        if not state['host_patch_present']:
            if not apply_host_patch:
                raise RuntimeError('Host support is missing; --apply-host-patch is an explicit source-change opt-in')
            if not self.git_check():
                raise RuntimeError('Host patch does not apply; preserve the checkout and review compatibility')
        backup = None
        if conflicts:
            backup_root = self.home / 'backups'
            if backup_root.is_symlink():
                raise ValueError('Linked backup destination is not accepted')
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix='hermes-review-', dir=backup_root))
            for target in conflicts:
                saved = backup / target.relative_to(self.home)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
        if not state['host_patch_present']:
            subprocess.run(['git', '-C', str(self.checkout), 'apply', str(self.patch)], check=True, timeout=15)
        for source, target in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.cli('enable', 'heretic-reviewer', '--no-allow-tool-override')
        plugins = json.loads(self.cli('list', '--json').stdout)
        matches = [plugin for plugin in plugins if plugin.get('name') == 'heretic-reviewer']
        if len(matches) != 1 or matches[0].get('status') != 'enabled':
            raise RuntimeError('Native plugin readback did not confirm enablement')
        result = self.check()
        if not result['host_patch_present'] or not result['package_files_match']:
            raise RuntimeError('Installed artifact readback failed')
        return {**result, 'enabled_for_next_load': True, 'backup': str(backup) if backup else None,
                'activation': 'next normal gateway start; no restart performed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'install'))
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--profile-home', type=Path, required=True)
    parser.add_argument('--apply-host-patch', action='store_true')
    parser.add_argument('--replace', action='store_true', help='Back up and replace only differing owned package files')
    parser.add_argument('--enable', action='store_true', help='Explicitly opt the selected profile into automatic local reviews')
    arguments = parser.parse_args()
    if arguments.action == 'install' and not arguments.enable:
        parser.error('install requires --enable; automatic local review is optional')
    logging.basicConfig(level=logging.INFO)
    installer = ReviewInstaller(Path(__file__).resolve().parents[1], arguments.checkout, arguments.profile_home)
    result = installer.check() if arguments.action == 'check' else installer.install(arguments.apply_host_patch, arguments.replace)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
