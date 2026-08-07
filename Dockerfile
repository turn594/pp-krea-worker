# FAST product fix: start from surgical image that already BOOTS (b5905da mini green)
# and only add Krea2 UNET detection + DiT module. No full Comfy replace, no torch reinstall.
# Last full overlay (e5a32fb) re-broke boot ("Comfy not reachable"). Do not repeat that.

FROM ghcr.io/turn594/pp-krea-worker:b5905da7fd0065041f59b69e6b7d2b795dcec3e8

USER root
ENV PATH="/opt/venv/bin:${PATH}"

# Matched Krea2 UNET stack only (detect + model_base + ldm/krea2)
RUN set -eux; \
  cd /tmp; \
  wget -qO comfy.tgz https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz; \
  tar xzf comfy.tgz; \
  SRC=/tmp/ComfyUI-master; \
  test -f "$SRC/comfy/ldm/krea2/model.py"; \
  cp -f "$SRC/comfy/model_detection.py" /comfyui/comfy/model_detection.py; \
  cp -f "$SRC/comfy/supported_models.py" /comfyui/comfy/supported_models.py; \
  cp -f "$SRC/comfy/model_base.py" /comfyui/comfy/model_base.py; \
  rm -rf /comfyui/comfy/ldm/krea2; \
  cp -a "$SRC/comfy/ldm/krea2" /comfyui/comfy/ldm/krea2; \
  # krea2 TE already on b5905da; ensure still present \
  test -f /comfyui/comfy/text_encoders/krea2.py; \
  grep -q krea2 /comfyui/comfy/model_detection.py; \
  grep -q 'class Krea2' /comfyui/comfy/supported_models.py; \
  grep -q 'class Krea2' /comfyui/comfy/model_base.py; \
  test -f /comfyui/custom_nodes/universal_seamless/comfy_universal_seamless.py; \
  rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master; \
  echo krea2_unet_surgical_ok

# Keep mini smoke file
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
