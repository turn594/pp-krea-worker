# Personal Paw — Krea UST serverless worker
# Models stay on Network Volume (/runpod-volume/models/...).
# Build via RunPod GitHub integration, CI, or pod+kaniko (see BUILD.md).
#
# Official path (RunPod docs / Assistant): custom image FROM worker-comfyui base.

ARG BASE_TAG=5.8.6-base
FROM runpod/worker-comfyui:${BASE_TAG}

USER root

# --- Upgrade ComfyUI core so CLIP type krea2 + qwen3vl TE exist ---
# 5.8.6 predates open-weight Krea2; master/recent release includes comfy.text_encoders.krea2
RUN set -eux; \
  cd /tmp; \
  wget -qO comfy.tgz https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz; \
  tar xzf comfy.tgz; \
  SRC=/tmp/ComfyUI-master; \
  test -d "$SRC/comfy"; \
  cp -a /comfyui/extra_model_paths.yaml /tmp/emp.yaml 2>/dev/null || true; \
  rm -rf /comfyui/comfy; \
  cp -a "$SRC/comfy" /comfyui/comfy; \
  for f in nodes.py folder_paths.py execution.py server.py main.py latent_preview.py cuda_malloc.py node_helpers.py; do \
    if [ -f "$SRC/$f" ]; then cp -f "$SRC/$f" /comfyui/; fi; \
  done; \
  for d in comfy_extras api_server app utils middleware; do \
    if [ -d "$SRC/$d" ]; then rm -rf "/comfyui/$d"; cp -a "$SRC/$d" "/comfyui/$d"; fi; \
  done; \
  if [ -f "$SRC/requirements.txt" ]; then \
    (uv pip install -r "$SRC/requirements.txt" || pip install -r "$SRC/requirements.txt" || true); \
  fi; \
  if [ -f /tmp/emp.yaml ]; then cp -f /tmp/emp.yaml /comfyui/extra_model_paths.yaml; fi; \
  python -c "import comfy.text_encoders.krea2; print('krea2_ok')"; \
  rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master

# Product wrap nodes (DiT seamless)
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/

# Volume path map (diffusion_models + text_encoders)
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Sanity: UST node file present (import needs torch/comfy at runtime)
RUN test -f /comfyui/custom_nodes/universal_seamless/__init__.py \
  && grep -q MakeCircularVAEDiT /comfyui/custom_nodes/universal_seamless/__init__.py \
  && echo "ust_nodes_ok"

# Keep stock entrypoint: /start.sh (handler + Comfy). Do NOT override CMD.
