# Layer 3: Comfy with krea2, without breaking worker-comfyui boot.
# Research (C stuck initializing): copying master /comfyui/comfy alone leaves the
# launch venv missing runtime deps — same class of issue documented in
# runpod-workers/worker-comfyui Dockerfile (start.sh uses /opt/venv; deps must match).
# Fix: after overlay, install ComfyUI requirements into the active venv.
# Still no separate torch 2.5 layer; product Turbo weights stay on the network volume.

FROM runpod/worker-comfyui:5.8.6-base

USER root

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Overlay ComfyUI sources (includes text_encoders/krea2.py for CLIP type krea2)
RUN set -eux; \
  cd /tmp; \
  wget -qO comfy.tgz https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz; \
  tar xzf comfy.tgz; \
  SRC=/tmp/ComfyUI-master; \
  test -d "$SRC/comfy"; \
  cp -a /comfyui/extra_model_paths.yaml /tmp/emp.yaml; \
  rm -rf /comfyui/comfy; \
  cp -a "$SRC/comfy" /comfyui/comfy; \
  for f in nodes.py folder_paths.py execution.py server.py main.py latent_preview.py cuda_malloc.py node_helpers.py requirements.txt; do \
    if [ -f "$SRC/$f" ]; then cp -f "$SRC/$f" /comfyui/; fi; \
  done; \
  for d in comfy_extras api_server app utils middleware; do \
    if [ -d "$SRC/$d" ]; then rm -rf "/comfyui/$d"; cp -a "$SRC/$d" "/comfyui/$d"; fi; \
  done; \
  cp -f /tmp/emp.yaml /comfyui/extra_model_paths.yaml; \
  test -f /comfyui/comfy/text_encoders/krea2.py; \
  # Critical: reinstall Comfy runtime deps into worker venv (official worker pattern)
  if [ -f /comfyui/requirements.txt ]; then \
    (uv pip install -r /comfyui/requirements.txt || pip install -r /comfyui/requirements.txt); \
  fi; \
  rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master /tmp/emp.yaml; \
  echo layer3_overlay_deps_ok

# Mini smoke for builder / cold path (no Turbo weights in image)
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
  && echo "layer3_krea2_ok"

# Official worker entrypoint
