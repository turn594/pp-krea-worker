# Ladder B — ONE layer past last green (14b93ee stock EmptyImage).
# Layer: + UST custom_nodes only.
# Fixed: grep the file that actually defines MakeCircularVAEDiT (not soft __init__).
# No torch upgrade, no Comfy master, no yaml, no pip — those are later steps.

FROM runpod/worker-comfyui:5.8.6-base

USER root

# UST DiT wrap nodes only
COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/

# Builder mini smoke (same as last green 14b93ee)
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

# Prove UST files landed (grep the implementation module, not soft-import __init__)
RUN test -f /comfyui/custom_nodes/universal_seamless/__init__.py \
  && test -f /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && grep -q MakeCircularVAEDiT /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py \
  && echo "ust_nodes_ok"

# Stock CMD/entrypoint only.
