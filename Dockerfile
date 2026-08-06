# Personal Paw serverless worker — product Krea stack (one image).
# Proven on pod: Comfy with krea2 + torch>=2.5 (enable_gqa) + UST DiT + volume models.
# Models stay on Network Volume (/runpod-volume). Do NOT bake multi-GB weights.
#
# Ladder: mini EmptyImage first, then krea2 type, then product graph.
# Keep stock entrypoint /start.sh — do not override CMD.

FROM runpod/worker-comfyui:5.8.6-base

USER root

# SDK volume bugfix (1.9.1–1.10.0)
RUN pip install -U 'runpod>=1.10.1' || uv pip install 'runpod>=1.10.1' || true

# Torch 2.5+ required: Comfy krea2 CLIP encode uses enable_gqa (fails on 2.4.x)
RUN pip install -U 'torch==2.5.1' 'torchvision==0.20.1' 'torchaudio==2.5.1' \
    --index-url https://download.pytorch.org/whl/cu124 \
    || true

# Upgrade ComfyUI core so CLIP type krea2 + qwen3vl TE exist (5.8.6 base is too old)
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
  python -c "import torch; assert hasattr(torch.nn.functional.scaled_dot_product_attention,'__call__'); print('torch', torch.__version__)"; \
  rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master

# Product wrap nodes (DiT seamless) — soft-fail import in package
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/

# Volume path map (diffusion_models + text_encoders + unet/clip/vae)
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Builder smoke: no multi-GB models required
RUN printf '%s\n' \
  '{' \
  '  "input": {' \
  '    "workflow": {' \
  '      "1": {"class_type": "EmptyImage", "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 0}},' \
  '      "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "rp_test"}}' \
  '    }' \
  '  }' \
  '}' > /test_input.json \
  && (cp -f /test_input.json /comfyui/test_input.json 2>/dev/null || true)

RUN test -f /comfyui/custom_nodes/universal_seamless/__init__.py \
  && grep -q MakeCircularVAEDiT /comfyui/custom_nodes/universal_seamless/__init__.py \
  && echo "ust_nodes_ok"

# Stock CMD/entrypoint only (handler + Comfy).
