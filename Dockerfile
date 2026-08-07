# Product worker: Krea2 Turbo needs current Comfy model detection + TE.
# L3 half-overlay previously failed with "ComfyUI not reachable" because
# start.sh launches with /opt/venv, not a random system pip.
# Fix (RunPod worker-comfyui DR-1170): after overlay, install Comfy
# requirements into /opt/venv (PATH=/opt/venv/bin).
#
# Models stay on network volume /runpod-volume.

FROM runpod/worker-comfyui:5.8.6-base

USER root

# Official launch venv (start.sh)
ENV PATH="/opt/venv/bin:${PATH}"

# --- Comfy master overlay + venv deps (product: krea2 detect + TE) ---
RUN set -eux; \
  cd /tmp; \
  wget -qO comfy.tgz https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz; \
  tar xzf comfy.tgz; \
  SRC=/tmp/ComfyUI-master; \
  test -d "$SRC/comfy"; \
  test -f "$SRC/comfy/text_encoders/krea2.py"; \
  cp -a /comfyui/extra_model_paths.yaml /tmp/emp.yaml 2>/dev/null || true; \
  rm -rf /comfyui/comfy; \
  cp -a "$SRC/comfy" /comfyui/comfy; \
  for f in nodes.py folder_paths.py execution.py server.py main.py latent_preview.py cuda_malloc.py node_helpers.py requirements.txt; do \
    if [ -f "$SRC/$f" ]; then cp -f "$SRC/$f" /comfyui/; fi; \
  done; \
  for d in comfy_extras api_server app utils middleware; do \
    if [ -d "$SRC/$d" ]; then rm -rf "/comfyui/$d"; cp -a "$SRC/$d" "/comfyui/$d"; fi; \
  done; \
  if [ -f /tmp/emp.yaml ]; then cp -f /tmp/emp.yaml /comfyui/extra_model_paths.yaml; fi; \
  # DR-1170: launch venv must get full Comfy deps
  if command -v uv >/dev/null 2>&1; then \
    uv pip install -r /comfyui/requirements.txt; \
    uv pip install "transformers>=4.50.3,<5" "huggingface-hub<1.0"; \
  else \
    pip install -r /comfyui/requirements.txt; \
    pip install "transformers>=4.50.3,<5" "huggingface-hub<1.0"; \
  fi; \
  test -f /comfyui/comfy/text_encoders/krea2.py; \
  grep -q krea2 /comfyui/comfy/model_detection.py; \
  grep -q 'class Krea2' /comfyui/comfy/supported_models.py; \
  rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master /tmp/emp.yaml; \
  echo comfy_overlay_venv_ok

# enable_gqa needs torch>=2.5
RUN set -eux; \
  if command -v uv >/dev/null 2>&1; then \
    uv pip install --force-reinstall \
      'torch==2.5.1' 'torchvision==0.20.1' 'torchaudio==2.5.1' \
      --index-url https://download.pytorch.org/whl/cu124; \
  else \
    pip install --force-reinstall \
      'torch==2.5.1' 'torchvision==0.20.1' 'torchaudio==2.5.1' \
      --index-url https://download.pytorch.org/whl/cu124; \
  fi; \
  python -c "import torch; v=torch.__version__.split('+')[0].split('.'); assert (int(v[0]),int(v[1]))>=(2,5), torch.__version__; print('torch', torch.__version__)"

# Product nodes + volume paths (after overlay so they stick)
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY custom_nodes/pp_krea2/ /comfyui/custom_nodes/pp_krea2/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

RUN test -f /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && test -f /comfyui/custom_nodes/pp_krea2/__init__.py \
  && test -f /comfyui/extra_model_paths.yaml \
  && grep -q diffusion_models /comfyui/extra_model_paths.yaml \
  && echo product_nodes_ok

# Builder mini smoke (no multi-GB weights)
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

# Stock worker entrypoint only
