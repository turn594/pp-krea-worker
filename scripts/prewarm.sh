#!/usr/bin/env bash
# RunPod Ask AI Action 2 (true cold ≤30s):
# 1) Start ComfyUI once (same pattern as official start.sh)
# 2) Prewarm product path (load UNet+TE+VAE into VRAM)
# 3) Start ONLY /handler.py poller — NEVER re-exec /start.sh (that restarts Comfy and drops VRAM)
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

# Match official worker-comfyui start.sh env
export COMFY_PORT="${COMFY_PORT:-8188}"
export COMFYUI_ADDRESS="127.0.0.1:${COMFY_PORT}"
export COMFY_HOST="127.0.0.1"
COMFY_PID_FILE="/tmp/comfyui.pid"
: "${COMFY_LOG_LEVEL:=INFO}"

# libtcmalloc if available (official start.sh)
if TCMALLOC="$(ldconfig -p 2>/dev/null | grep -Po 'libtcmalloc.so.\d' | head -n 1 || true)"; then
  if [[ -n "${TCMALLOC:-}" ]]; then
    export LD_PRELOAD="${TCMALLOC}"
  fi
fi

# Optional offline manager mode
comfy-manager-set-mode offline 2>/dev/null || true

echo "[prewarm] starting ComfyUI once (keep alive for handler)"
cd /comfyui
python -u main.py --disable-auto-launch --disable-metadata --listen 127.0.0.1 --port "$COMFY_PORT" --verbose "${COMFY_LOG_LEVEL}" --log-stdout \
  >/tmp/prewarm-comfy.log 2>&1 &
COMFY_PID=$!
echo "$COMFY_PID" > "$COMFY_PID_FILE"
echo "[prewarm] comfy pid $COMFY_PID (file $COMFY_PID_FILE)"

# Wait for Comfy HTTP (boot budget, not customer gen)
ok=0
for i in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:${COMFY_PORT}/system_stats" >/dev/null 2>&1 \
    || curl -sf "http://127.0.0.1:${COMFY_PORT}/" >/dev/null 2>&1; then
    ok=1
    break
  fi
  if ! kill -0 "$COMFY_PID" 2>/dev/null; then
    echo "[prewarm] comfy died during boot"
    tail -n 100 /tmp/prewarm-comfy.log || true
    exit 1
  fi
  sleep 1
done
if [[ "$ok" != "1" ]]; then
  echo "[prewarm] comfy not up in 120s — see /tmp/prewarm-comfy.log"
  tail -n 100 /tmp/prewarm-comfy.log || true
  exit 1
fi

echo "[prewarm] VRAM before warmup:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi n/a"

echo "[prewarm] running product-path warmup workflow (cap 90s so handler can poll)"
# If warmup hangs on volume I/O, jobs sit IN_QUEUE forever while worker looks "running".
# Cap prewarm so poller starts; first product may be slower but assign works.
if timeout 90s python -u /prewarm_prompt.py; then
  echo "[prewarm] warmup OK"
else
  echo "[prewarm] warmup failed/timeout — keep Comfy, start handler (degraded; FlashBoot still forms after first real job)"
fi

echo "[prewarm] VRAM after warmup:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi n/a"

date -Is > /tmp/prewarm_done
echo "[prewarm] done $(cat /tmp/prewarm_done) — keep Comfy PID $COMFY_PID"

# Decisive rule: start poller ONLY. Never exec /start.sh (it restarts Comfy → cold reload).
if [[ ! -f /handler.py ]]; then
  echo "[prewarm] FATAL: /handler.py missing — cannot start poller without restarting Comfy"
  ls -la / | head -n 50 || true
  find / -name 'handler.py' -o -name 'rp_handler.py' 2>/dev/null | head -n 20 || true
  exit 1
fi

echo "[prewarm] VRAM before handler poller:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi n/a"

echo "[prewarm] exec python -u /handler.py (Comfy stays up, models in VRAM)"
exec python -u /handler.py
