# Product-capable slim: official base + nodes + baked Krea2 TE stack + runpod pin.
# No full Comfy master overlay (that image stuck initializing / no assign).
# Assign-proven path: stock /start.sh only.
ARG BASE_TAG=5.8.6-base
FROM runpod/worker-comfyui:${BASE_TAG}

USER root

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY custom_nodes/pp_krea2/ /comfyui/custom_nodes/pp_krea2/
COPY vendor/text_encoders/ /tmp/vendor_te/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Bake TE stack into stock Comfy 5.8.6 (missing qwen3vl / krea2 / VL helpers).
# All files from build context — no network at image build time.
RUN set -eux; \
  TE=/comfyui/comfy/text_encoders; \
  NODE=/comfyui/custom_nodes/pp_krea2; \
  test -d "$TE"; \
  test -d "$NODE"; \
  cp -f /tmp/vendor_te/qwen_vl.py "$TE/qwen_vl.py"; \
  cp -f /tmp/vendor_te/qwen35.py "$TE/qwen35.py"; \
  cp -f "$NODE/qwen3vl.py" "$TE/qwen3vl.py"; \
  cp -f "$NODE/llama.py" "$TE/llama.py"; \
  cp -f "$NODE/qwen_image.py" "$TE/qwen_image.py"; \
  cp -f "$NODE/hunyuan_video.py" "$TE/hunyuan_video.py"; \
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
