# Local image generation and editing

Local inference setup for Apple Silicon. Read `LOCAL_SETUP.md` for normal use
and known limits. This directory contains portable source and configuration.
Weights, private prompts, images, logs and environments remain outside Git.

## Contents

- `models.lock.json`: exact model revisions, file sizes and SHA256 values.
- `requirements-mflux.lock`, `requirements-gui.lock`: installed dependencies.
- `upstream.json`, `mflux-paint.patch`: pinned GUI source and focused local patch.
- `verify_models.py`: complete installed-weight checksum verification.
- `verify_presets.py`: installed preset, Finder PATH and command checks.
- `mflux-conditioning.patch`, `mflux-conditioning.json`: runtime fix and exact source hashes.
- `apply_runtime_patch.py`, `verify_conditioning.py`: guarded installation and weight-free regressions.
- `lightning-setup.json`, `lightning_scheduler.py`: pinned four-step adapter and author-compatible schedule.
- `verify_app_runtime.py --run-inference`: one explicit live 512-pixel application mask/save check.

## Restore on another Apple Silicon Mac

These commands target a new installation. Do not overwrite an existing app or
checkout. Start from the root of this setup repository. The existing installation
was exercised; a clean machine restore still requires its own runtime check.

```sh
SETUP="$PWD/models/image-generation"
APP_SOURCE="$HOME/.local/share/local-image-studio/app"
MODELS="$HOME/.local/share/local-image-studio/models"
ADAPTERS="$HOME/.local/share/local-image-studio/adapters"

uv tool install --python 3.13.18 --constraints "$SETUP/requirements-mflux.lock" 'mflux==0.24.0'
"$HOME/.local/share/uv/tools/mflux/bin/python" "$SETUP/apply_runtime_patch.py"
"$HOME/.local/share/uv/tools/mflux/bin/python" "$SETUP/verify_conditioning.py"
"$HOME/.local/share/uv/tools/mflux/bin/python" "$SETUP/verify_lightning.py"
mkdir -p "$MODELS"
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 \
  "$HOME/.local/share/uv/tools/mflux/bin/hf" download \
  mflux-community/qwen-image-2512-mflux-q6 \
  --revision a749a846189626f339c0ee7463274fd3c00e97bd \
  --local-dir "$MODELS/qwen-image-2512-mflux-q6"
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 \
  "$HOME/.local/share/uv/tools/mflux/bin/hf" download \
  mflux-community/qwen-image-edit-2511-mflux-q8 \
  --revision 087317af06b8b2d197f21596d6ae1cd5b1b1c902 \
  --local-dir "$MODELS/qwen-image-edit-2511-mflux-q8"
"$HOME/.local/share/uv/tools/mflux/bin/python" "$SETUP/verify_models.py"

HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 \
  "$HOME/.local/share/uv/tools/mflux/bin/hf" download lightx2v/Qwen-Image-Lightning \
  Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors \
  --revision d468c534b360e0754c6bf9e38ed49e1e09cd2e2a --local-dir "$ADAPTERS/download"
cp "$ADAPTERS/download/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors" "$ADAPTERS/"
printf '%s  %s\n' 2a32ce938ec71db2b49a817b4844ae86995569518dea56ee0ddc209cbe8e1377 \
  "$ADAPTERS/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors" | shasum -a 256 -c -

git clone https://github.com/Amo643/mflux-paint.git "$APP_SOURCE"
git -C "$APP_SOURCE" checkout --detach 2d5db24942d50b0e8561ee5c4b7e11049b67302a
git -C "$APP_SOURCE" apply --check "$SETUP/mflux-paint.patch"
git -C "$APP_SOURCE" apply "$SETUP/mflux-paint.patch"
cp "$SETUP/LOCAL_SETUP.md" "$APP_SOURCE/LOCAL_SETUP.md"
uv venv --python 3.13.18 "$APP_SOURCE/.venv"
uv pip sync --python "$APP_SOURCE/.venv/bin/python" "$SETUP/requirements-gui.lock"
"$APP_SOURCE/.venv/bin/python" "$SETUP/verify_presets.py"
bash "$APP_SOURCE/build.sh" "$HOME/Applications/MFLUX Paint.app"
```

The upstream build replaces its destination and closes matching running app
windows. Use it only when no image job or desktop window is active. For source
restoration testing, use a disposable checkout and compare patched source bytes;
do not run its destructive installer against a working application.

## Verification records

Synthetic acceptance images stay in `$HOME/Pictures/Local Image Studio/acceptance`.
The generation and two-reference smoke tests completed offline. Full-resolution
masked editing is a separate acceptance gate; consult `acceptance.json` when
present, rather than treating downloaded weights or a running job as completion.
