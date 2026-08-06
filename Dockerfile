FROM runpod/worker-comfyui:5.8.6-base

USER root

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

RUN test -f /comfyui/custom_nodes/universal_seamless/__init__.py
