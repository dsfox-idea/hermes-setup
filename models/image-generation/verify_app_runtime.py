import argparse
import base64
import importlib.util
import io
import json
from pathlib import Path
import threading
import time
import urllib.request

import numpy as np
from PIL import Image, ImageChops, ImageDraw


class AppAcceptance:
    @staticmethod
    def encode(image):
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()

    def run(self):
        folder = Path.home() / 'Pictures/Local Image Studio/acceptance'
        path = Path.home() / 'Applications/MFLUX Paint.app/Contents/Resources/server.py'
        spec = importlib.util.spec_from_file_location('paint_acceptance', path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.MODELS['qwen-edit']['steps'] == 4
        assert module.MODELS['qwen-edit']['guidance'] == 1.0
        completed = threading.Event()
        original_update = module._jset

        def observe(job_id, **changes):
            original_update(job_id, **changes)
            if changes.get('status') in ('done', 'error'):
                completed.set()

        module._jset = observe
        server = module.Server(('127.0.0.1', 0), module.H)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        endpoint = f'http://127.0.0.1:{server.server_port}'
        job = None
        started = time.monotonic()
        try:
            image = Image.open(folder / '01-generated.png').convert('RGB').resize((512, 512))
            mask = Image.new('L', image.size, 0)
            ImageDraw.Draw(mask).rectangle((50, 140, 465, 430), fill=255)
            payload = {'model': 'qwen-edit', 'prompt': 'Change the red teapot to cobalt blue. Preserve its shape and background.',
                       'steps': 4, 'guidance': 1.0, 'size': 512, 'seed': '42',
                       'image': self.encode(image), 'mask': self.encode(mask)}
            request = urllib.request.Request(endpoint+'/run', data=json.dumps(payload).encode(),
                                             headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=10) as response:
                job = json.load(response)['job']
            if not completed.wait(600):
                raise TimeoutError('Application inference exceeded the acceptance deadline')
            with urllib.request.urlopen(endpoint+'/progress?job='+job, timeout=10) as response:
                data = json.load(response)
            if data['status'] != 'done':
                raise RuntimeError({key: value for key, value in data.items() if key != 'images'})
            assert len(data['images']) == 1
            result = Image.open(io.BytesIO(base64.b64decode(data['images'][0].split(',',1)[1]))).convert('RGB')
            assert result.size == image.size
            difference = ImageChops.difference(result, image)
            assert difference.getbbox() is not None
            assert difference.crop((0,0,512,100)).getbbox() is None
            assert difference.crop((0,480,512,512)).getbbox() is None
            before, after = np.asarray(image).astype(float), np.asarray(result).astype(float)
            red = (before[:,:,0] > before[:,:,1]*1.5) & (before[:,:,0] > before[:,:,2]*1.5)
            blue_fraction = float(np.mean(after[:,:,2][red] > after[:,:,0][red]))
            assert blue_fraction > .8
            save_request = urllib.request.Request(endpoint+'/save',
                data=json.dumps({'image': data['images'][0], 'name': 'acceptance-gui-lightning-'+job+'.png'}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(save_request, timeout=10) as response:
                saved = Path(json.load(response)['path'])
            assert ImageChops.difference(Image.open(saved).convert('RGB'),result).getbbox() is None
            result.save(folder/'gui-lightning-mask.png')
            receipt = {'status':'passed','dimensions':[512,512],'steps':4,'seconds':round(time.monotonic()-started,2),
                       'outside_feathered_mask_pixel_exact':True,'red_pixels_changed_to_blue_fraction':blue_fraction,
                       'saved_file_readback':'pixel_exact','saved_name':saved.name}
            (folder/'gui-lightning-acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(json.dumps(receipt),flush=True)
        finally:
            if job is not None:
                process = module.JOBS.get(job, {}).get('_proc')
                if process is not None and process.poll() is None:
                    process.terminate()
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run one real 512-pixel application inference and verify mask/save behavior.')
    parser.add_argument('--run-inference', action='store_true', required=True)
    parser.parse_args()
    AppAcceptance().run()
