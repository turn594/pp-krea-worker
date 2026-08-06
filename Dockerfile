# B-infra / mini cold ladder image.
# Layer 1 only: stock worker + UST nodes + volume paths + SDK fix.
# NO full Comfy master upgrade / torch 908MB wheel here (that failed RunPod buildx).
# After mini on/off/cold is GREEN, next commit adds krea2-era Comfy+torch as layer 2.

FROM runpod/worker-comfyui:5.8.6-base

USER root

# Network-volume job tracking fix
RUN pip install -U 'runpod>=1.10.1' || true

# Product wrap nodes (soft-fail import)
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/

# Volume model paths for serverless mount /runpod-volume
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Builder / mini smoke — no multi-GB models
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

# Stock entrypoint only
