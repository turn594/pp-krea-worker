# STEP 1 only — prove a GitHub-built image from official base can run.
# No custom nodes, no yaml overwrite, no Comfy upgrade.
# After this smokes green, next commit adds ONE layer.

FROM runpod/worker-comfyui:5.8.6-base

# Replace default test workflow so RunPod builder smoke doesn't need models.
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

# Stock CMD/entrypoint only.
