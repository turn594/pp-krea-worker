# Product-capable slim: official base + nodes + baked Krea2 TE stack + runpod pin.
# No full Comfy master overlay (that image stuck initializing / no assign).
# Assign-proven path: stock /start.sh only.
ARG BASE_TAG=5.8.6-base
FROM runpod/worker-comfyui:${BASE_TAG}

USER root

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY custom_nodes/pp_krea2/ /comfyui/custom_nodes/pp_krea2/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Bake TE stack into stock Comfy 5.8.6 (missing qwen3vl / krea2 / VL helpers).
# Do not import comfy at build time (package lives under /comfyui, not site-packages).
RUN set -eux; \
  TE=/comfyui/comfy/text_encoders; \
  NODE=/comfyui/custom_nodes/pp_krea2; \
  test -d "$TE"; \
  test -d "$NODE"; \
  BASE=https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/comfy/text_encoders; \
  for f in qwen_vl.py qwen35.py; do \
    wget -qO "$TE/$f" "$BASE/$f"; \
  done; \
  for f in qwen3vl.py llama.py qwen_image.py hunyuan_video.py; do \
    cp -f "$NODE/$f" "$TE/$f"; \
  done; \
  cp -f "$NODE/krea2_te.py" "$TE/krea2.py"; \
  test -s "$TE/qwen_vl.py"; \
  test -s "$TE/qwen35.py"; \
  test -s "$TE/qwen3vl.py"; \
  test -s "$TE/krea2.py"; \
  test -s "$TE/llama.py"; \
  ls -la "$TE"/qwen*.py "$TE"/krea2.py "$TE"/llama.py; \
  test -f /start.sh; \
  test -f /handler.py; \
  test -f /comfyui/custom_nodes/pp_krea2/__init__.py; \
  test -f /comfyui/custom_nodes/universal_seamless/__init__.py; \
  grep -q MakeCircularVAEDiT /comfyui/custom_nodes/universal_seamless/__init__.py; \
  (uv pip install --system 'runpod>=1.10.1' || pip install -U 'runpod>=1.10.1'); \
  python -c "import importlib.metadata as m; v=m.version('runpod'); print('runpod', v); assert tuple(int(x) for x in v.split('.')[:3]) >= (1, 10, 1), v"

CMD ["/start.sh"]
