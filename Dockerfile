FROM runpod/worker-comfyui:5.8.6-base

USER root

# Network-volume endpoints need runpod>=1.10.1 (1.9.1-1.10.0 job-tracking bug).
# Per RunPod Assistant / docs serverless troubleshooting.
RUN pip install --no-cache-dir "runpod>=1.10.1" \
  || uv pip install --system "runpod>=1.10.1" \
  || true
RUN python -c "import runpod; print('runpod', getattr(runpod, '__version__', '?'))"

COPY custom_nodes/universal_seamless/ /comfyui/custom_nodes/universal_seamless/
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

RUN test -f /comfyui/custom_nodes/universal_seamless/__init__.py
# Do not override CMD/entrypoint — keep stock worker-comfyui /start.sh
