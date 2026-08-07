#!/usr/bin/env bash
# Fast cold start: NEVER block on multi-GB copy before the handler is up.
# Volume paths via extra_model_paths (source of truth). Hardlink-only optional
# local aliases (no cp). Background hardlink attempt must not delay /start.sh.
# Customer bar ~20s — a full cp of turbo weights alone blows the bar.
set -euo pipefail

VOL="${RUNPOD_VOLUME_PATH:-/runpod-volume}/models"
LOCAL="/comfyui/models"

mkdir -p \
  "$LOCAL/diffusion_models" \
  "$LOCAL/text_encoders" \
  "$LOCAL/vae" \
  "$LOCAL/unet" \
  "$LOCAL/clip" \
  "$LOCAL/loras"

# Volume first (always present on this endpoint) + local aliases if hardlinked later
cat > /comfyui/extra_model_paths.yaml <<'YAML'
runpod_worker_comfy:
  base_path: /runpod-volume
  checkpoints: models/checkpoints/
  clip: models/clip/
  text_encoders: models/text_encoders/
  clip_vision: models/clip_vision/
  configs: models/configs/
  controlnet: models/controlnet/
  embeddings: models/embeddings/
  loras: models/loras/
  upscale_models: models/upscale_models/
  vae: models/vae/
  unet: models/unet/
  diffusion_models: models/diffusion_models/

pp_local_hot:
  base_path: /comfyui/
  checkpoints: models/checkpoints/
  clip: models/clip/
  text_encoders: models/text_encoders/
  clip_vision: models/clip_vision/
  configs: models/configs/
  controlnet: models/controlnet/
  embeddings: models/embeddings/
  loras: models/loras/
  upscale_models: models/upscale_models/
  vae: models/vae/
  unet: models/unet/
  diffusion_models: models/diffusion_models/
YAML

# Non-blocking: hardlink only (no cp). Failure is fine — volume path works.
(
  hardlink() {
    local rel="$1"
    local src="$VOL/$rel"
    local dst="$LOCAL/$rel"
    [[ -f "$dst" ]] && return 0
    [[ -f "$src" ]] || return 0
    ln "$src" "$dst" 2>/dev/null || true
  }
  hardlink "diffusion_models/krea2_turbo_fp8_scaled.safetensors"
  hardlink "text_encoders/qwen3vl_4b_fp8_scaled.safetensors"
  hardlink "vae/qwen_image_vae.safetensors"
  if [[ -f "$LOCAL/diffusion_models/krea2_turbo_fp8_scaled.safetensors" && ! -e "$LOCAL/unet/krea2_turbo_fp8_scaled.safetensors" ]]; then
    ln -sf ../diffusion_models/krea2_turbo_fp8_scaled.safetensors "$LOCAL/unet/krea2_turbo_fp8_scaled.safetensors" 2>/dev/null || true
  fi
  if [[ -f "$LOCAL/text_encoders/qwen3vl_4b_fp8_scaled.safetensors" && ! -e "$LOCAL/clip/qwen3vl_4b_fp8_scaled.safetensors" ]]; then
    ln -sf ../text_encoders/qwen3vl_4b_fp8_scaled.safetensors "$LOCAL/clip/qwen3vl_4b_fp8_scaled.safetensors" 2>/dev/null || true
  fi
  echo "[pp-flash] bg hardlink pass done"
) >/tmp/pp-flash-stage.log 2>&1 &

# RunPod Ask AI (2026-08-07): do not read weights from network volume during request
# hot path. Prefer local hardlinks. Full cp only if hardlink fails AND file small enough
# would blow SLA — so we only hardlink; volume remains fallback via yaml above.
echo "[pp-flash] exec stock /start.sh immediately (handler ready before model load)"
exec /start.sh
