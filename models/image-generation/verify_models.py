import argparse
import hashlib
import json
from pathlib import Path


class ModelVerifier:
    def __init__(self, directory):
        self.directory = directory
        self.manifest = json.loads(Path(__file__).with_name('models.lock.json').read_text())

    def run(self):
        count = 0
        total_bytes = 0
        for model in self.manifest:
            folder = self.directory / model['repo'].split('/')[-1]
            for entry in model['files']:
                target = folder / entry['path']
                if target.stat().st_size != entry['bytes']:
                    raise ValueError(f'Size mismatch: {target}')
                with target.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != entry['sha256']:
                    raise ValueError(f'SHA256 mismatch: {target}')
                count += 1
                total_bytes += entry['bytes']
        print(json.dumps({'models': len(self.manifest), 'files_verified': count,
                          'bytes_verified': total_bytes, 'status': 'passed'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify pinned local image model files.')
    parser.add_argument('--model-dir', type=Path,
                        default=Path.home() / '.local/share/local-image-studio/models')
    ModelVerifier(parser.parse_args().model_dir).run()
