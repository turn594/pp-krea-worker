# Layer 3 past green layer2 (aa7af47 paths).
# THIS LAYER ONLY: upgrade ComfyUI core for native CLIP type krea2.
# Still no torch 2.5 pip wheel (next layer if needed after this gates).

FROM runpod/worker-comfyui:5.8.6-base

USER root

# Layer1: UST
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/

# Layer2: volume paths
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Layer3: ComfyUI master overlay for krea2 / qwen3vl TE support
RUN set -eux; \
  cd /tmp; \
  wget -qO comfy.tgz https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz; \
  tar xzf comfy.tgz; \
  SRC=/tmp/ComfyUI-master; \
  test -d "$SRC/comfy"; \
  cp -a /comfyui/extra_model_paths.yaml /tmp/emp.yaml; \
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
  cp -f /tmp/emp.yaml /comfyui/extra_model_paths.yaml; \
  test -f /comfyui/comfy/text_encoders/krea2.py; \
  PYTHONPATH=/comfyui python -c "import comfy.text_encoders.krea2; print('krea2_ok')"; \
  rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master /tmp/emp.yaml

# Mini smoke (no multi-GB models)
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

RUN test -f /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && test -f /comfyui/extra_model_paths.yaml \
  && test -f /comfyui/comfy/text_encoders/krea2.py \
  && PYTHONPATH=/comfyui python -c "import comfy.text_encoders.krea2" \
  && echo "layer3_krea2_ok"

# Stock entrypoint only.
