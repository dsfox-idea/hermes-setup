import argparse
import hashlib
from importlib.metadata import version
from importlib.util import find_spec
import json
from pathlib import Path
import subprocess


class RuntimePatch:
    def run(self, target=None):
        artifacts = Path(__file__).resolve().parent
        manifest = json.loads((artifacts / 'mflux-conditioning.json').read_text())
        if version('mflux') != manifest['version']:
            raise RuntimeError('Patch requires the pinned MFLUX version')
        if target is None:
            spec = find_spec('mflux')
            if spec is None or spec.origin is None:
                raise RuntimeError('MFLUX installation not found')
            target = Path(spec.origin).parent.parent
        target = target.resolve()
        patch = artifacts / 'mflux-conditioning.patch'
        if hashlib.sha256(patch.read_bytes()).hexdigest() != manifest['patch_sha256']:
            raise RuntimeError('Patch checksum mismatch')
        scheduler = (artifacts / 'lightning_scheduler.py').read_bytes()
        if hashlib.sha256(scheduler).hexdigest() != manifest['helper_sha256']:
            raise RuntimeError('Scheduler checksum mismatch')
        scheduler_target = (target / 'lightning_scheduler.py').resolve()
        if not scheduler_target.is_relative_to(target):
            raise RuntimeError('Scheduler target escapes installation')
        if scheduler_target.exists() and scheduler_target.read_bytes() != scheduler:
            raise RuntimeError('Existing scheduler differs; refusing to overwrite')
        for name in manifest['files']:
            if not (target / name).resolve().is_relative_to(target):
                raise RuntimeError('Patch target escapes installation')
        actual = self.hashes(target, manifest)
        if all(actual[name] == expected['after'] for name, expected in manifest['files'].items()):
            self.install_scheduler(scheduler_target, scheduler)
            print('Conditioning patch already installed and verified')
            return
        if not all(actual[name] == expected['before'] for name, expected in manifest['files'].items()):
            raise RuntimeError('Source differs from the verified baseline; refusing to overwrite')
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=target, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=target, check=True)
        actual = self.hashes(target, manifest)
        if not all(actual[name] == expected['after'] for name, expected in manifest['files'].items()):
            raise RuntimeError('Patched source verification failed')
        self.install_scheduler(scheduler_target, scheduler)
        print('Conditioning patch applied and verified')

    @staticmethod
    def install_scheduler(target, contents):
        if not target.exists():
            target.write_bytes(contents)
        if target.read_bytes() != contents:
            raise RuntimeError('Installed scheduler verification failed')

    @staticmethod
    def hashes(target, manifest):
        return {name: hashlib.sha256((target / name).read_bytes()).hexdigest()
                for name in manifest['files']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Apply the verified local MFLUX conditioning patch.')
    parser.add_argument('--target', type=Path, help='Alternative package root for isolated restoration tests')
    RuntimePatch().run(parser.parse_args().target)
