# FROM known-booting surgical image. ONLY add custom node code (no core patches).
# PPKrea2UNETLoader registers Krea2 at job runtime so EmptyImage/boot stays clean.
# pp_flash_start.sh: stage hot-path weights to local disk so FlashBoot can wake fast
# (network volume alone kills cold start — enterprise pattern: local bytes + FlashBoot).

FROM ghcr.io/turn594/pp-krea-worker:b5905da7fd0065041f59b69e6b7d2b795dcec3e8

USER root

COPY custom_nodes/pp_krea2/ /comfyui/custom_nodes/pp_krea2/
COPY scripts/pp_flash_start.sh /pp_flash_start.sh
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Network-volume + serverless job tracking: runpod 1.9.1–1.10.0 can leave
# jobs IN_QUEUE while workers show ready. Pin fixed SDK. Do not block cold start.
RUN set -eux; \
  (uv pip install --system 'runpod>=1.10.1' || pip install -U 'runpod>=1.10.1'); \
  python -c "import importlib.metadata as m; print('runpod', m.version('runpod'))"; \
  chmod +x /pp_flash_start.sh; \
  test -f /comfyui/custom_nodes/pp_krea2/__init__.py; \
  test -f /comfyui/custom_nodes/pp_krea2/krea2_dit/model.py; \
  grep -q PPKrea2UNETLoader /comfyui/custom_nodes/pp_krea2/__init__.py; \
  echo pp_krea2_unet_node_ok

# Fast entry: volume paths + immediate /start.sh (no multi-GB cp before ready)
CMD ["/pp_flash_start.sh"]
