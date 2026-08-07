# Layer 3 SURGICAL — product krea2 without full Comfy overlay.
#
# Research (why L3 overlay RED "ComfyUI server not reachable"):
# Official runpod-workers/worker-comfyui Dockerfile (DR-1170): start.sh launches
# Comfy with /opt/venv, not /comfyui/.venv. Replacing /comfyui/comfy wholesale
# desyncs runtime deps → crash → worker shows ready but Comfy is dead.
# L1/L2 (UST + paths only) were GREEN. Product needs krea2 + torch>=2.5 (enable_gqa).
#
# This image:
#  1) Keeps stock 5.8.6-base boot path
#  2) UST + extra_model_paths (L1/L2 green)
#  3) Surgical krea2 only (file + type registration) + pp_krea2 custom node fallback
#  4) torch 2.5.1 into /opt/venv (the venv start.sh uses)
# Models stay on network volume /runpod-volume — not baked.

FROM runpod/worker-comfyui:5.8.6-base

USER root

# Launch venv first (same as official start.sh / Dockerfile)
ENV PATH="/opt/venv/bin:${PATH}"

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY custom_nodes/pp_krea2/ /comfyui/custom_nodes/pp_krea2/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY scripts/surgical_krea2.py /tmp/surgical_krea2.py

# Surgical krea2 registration (no full tree replace)
RUN python /tmp/surgical_krea2.py \
  && rm -f /tmp/surgical_krea2.py \
  && test -f /comfyui/comfy/text_encoders/krea2.py \
  && test -f /comfyui/custom_nodes/pp_krea2/__init__.py \
  && test -f /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && test -f /comfyui/extra_model_paths.yaml \
  && echo layer3_surgical_files_ok

# enable_gqa needs torch>=2.5 — install into /opt/venv only
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
  python -c "import torch; v=torch.__version__; print('torch', v); major,minor=map(int,v.split('+')[0].split('.')[:2]); assert (major,minor)>=(2,5), v"

# Mini smoke for builder (no multi-GB weights)
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

# Official worker entrypoint only — do not override CMD
