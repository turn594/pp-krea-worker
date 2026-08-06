FROM runpod/worker-comfyui:5.8.6-base

USER root

# Upgrade ComfyUI package tree so CLIP type krea2 + qwen3vl exist.
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates && rm -rf /var/lib/apt/lists/*
RUN wget -O /tmp/comfy.tgz https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz
RUN tar xzf /tmp/comfy.tgz -C /tmp
RUN test -f /tmp/ComfyUI-master/comfy/text_encoders/krea2.py
RUN test -f /tmp/ComfyUI-master/comfy/text_encoders/qwen3vl.py
RUN rm -rf /comfyui/comfy && cp -a /tmp/ComfyUI-master/comfy /comfyui/comfy
RUN for f in nodes.py folder_paths.py execution.py server.py main.py latent_preview.py cuda_malloc.py node_helpers.py; do if [ -f /tmp/ComfyUI-master/$f ]; then cp -f /tmp/ComfyUI-master/$f /comfyui/; fi; done
RUN for d in comfy_extras api_server app utils middleware; do if [ -d /tmp/ComfyUI-master/$d ]; then rm -rf /comfyui/$d && cp -a /tmp/ComfyUI-master/$d /comfyui/$d; fi; done
RUN PYTHONPATH=/comfyui python -c "import comfy.text_encoders.krea2; import comfy.text_encoders.qwen3vl; print('krea2_ok')"
RUN rm -rf /tmp/comfy.tgz /tmp/ComfyUI-master

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

RUN test -f /comfyui/custom_nodes/universal_seamless/__init__.py && grep -q MakeCircularVAEDiT /comfyui/custom_nodes/universal_seamless/__init__.py
