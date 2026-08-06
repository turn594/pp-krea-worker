# Layer 2 past green UST-only gate (ced020b).
# THIS LAYER ONLY: + extra_model_paths.yaml for /runpod-volume models.
# Still no torch upgrade, no Comfy master, no pip.

FROM runpod/worker-comfyui:5.8.6-base

USER root

# UST DiT wrap nodes (layer 1 — already gated)
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/

# Layer 2: volume model path map only
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Builder mini smoke
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
  && test -f /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && grep -q MakeCircularVAEDiT /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && test -f /comfyui/extra_model_paths.yaml \
  && grep -q diffusion_models /comfyui/extra_model_paths.yaml \
  && echo "layer2_paths_ok"

# Stock CMD/entrypoint only.
