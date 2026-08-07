#!/usr/bin/env bash
# RunPod Ask AI pattern (2026-08-07): do NOT start handler until prewarm done.
# Then exec official /start.sh so ready means models already exercised.
set -euo pipefail

echo "[prewarm] boot $(date -Is)"
date -Is > /tmp/boot_id

VOL="${RUNPOD_VOLUME_PATH:-/runpod-volume}/models"
LOCAL="/comfyui/models"
mkdir -p "$LOCAL/diffusion_models" "$LOCAL/text_encoders" "$LOCAL/vae" "$LOCAL/unet" "$LOCAL/clip"

# Prefer local hardlinks (no multi-GB cp on critical path)
hl() {
  local rel="$1"
  local src="$VOL/$rel"
  local dst="$LOCAL/$rel"
  [[ -f "$dst" ]] && return 0
  [[ -f "$src" ]] || return 0
  ln "$src" "$dst" 2>/dev/null || true
}
hl "diffusion_models/krea2_turbo_fp8_scaled.safetensors"
hl "text_encoders/qwen3vl_4b_fp8_scaled.safetensors"
hl "vae/qwen_image_vae.safetensors"

# Volume + local path map
cat > /comfyui/extra_model_paths.yaml <<'YAML'
runpod_worker_comfy:
  base_path: /runpod-volume
  diffusion_models: models/diffusion_models/
  text_encoders: models/text_encoders/
  vae: models/vae/
  unet: models/unet/
  clip: models/clip/
  loras: models/loras/
pp_local_hot:
  base_path: /comfyui/
  diffusion_models: models/diffusion_models/
  text_encoders: models/text_encoders/
  vae: models/vae/
  unet: models/unet/
  clip: models/clip/
  loras: models/loras/
YAML

# Start Comfy only for prewarm (handler not running yet)
export COMFY_PORT="${COMFY_PORT:-8188}"
cd /comfyui
python main.py --listen 127.0.0.1 --port "$COMFY_PORT" --disable-auto-launch >/tmp/prewarm-comfy.log 2>&1 &
COMFY_PID=$!
echo "[prewarm] comfy pid $COMFY_PID"

# Wait for Comfy HTTP (cap 90s — this is boot, not customer gen)
ok=0
for i in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:${COMFY_PORT}/system_stats" >/dev/null 2>&1 \
    || curl -sf "http://127.0.0.1:${COMFY_PORT}/" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" != "1" ]]; then
  echo "[prewarm] comfy not up — see /tmp/prewarm-comfy.log"
  tail -n 80 /tmp/prewarm-comfy.log || true
  kill "$COMFY_PID" 2>/dev/null || true
  echo "[prewarm] continuing to /start.sh without prewarm (degraded)"
  exec /start.sh
fi

echo "[prewarm] running tiny product-path workflow"
python -u /prewarm_prompt.py || {
  echo "[prewarm] prompt failed — continue to start.sh"
  kill "$COMFY_PID" 2>/dev/null || true
  wait "$COMFY_PID" 2>/dev/null || true
  exec /start.sh
}

date -Is > /tmp/prewarm_done
echo "[prewarm] done $(cat /tmp/prewarm_done) — keep Comfy PID $COMFY_PID (models in VRAM)"

# Do NOT kill Comfy: killing drops VRAM and first product reloads >30s.
# Start serverless handler only if present; else fall back to start.sh (degraded).
export COMFYUI_ADDRESS="127.0.0.1:${COMFY_PORT}"
export COMFY_HOST="127.0.0.1"
export COMFY_PORT

for h in /handler.py /rp_handler.py /comfyui/handler.py /workspace/handler.py; do
  if [[ -f "$h" ]]; then
    echo "[prewarm] exec handler $h with existing Comfy"
    exec python -u "$h"
  fi
done

echo "[prewarm] no standalone handler — start.sh (may restart Comfy)"
# Prefer start.sh without restarting comfy if it checks port
if ss -lnt | grep -q ":${COMFY_PORT}"; then
  echo "[prewarm] comfy already listening; try start.sh anyway"
fi
exec /start.sh
