# FROM known-booting surgical image. ONLY add custom node code (no core patches).
# PPKrea2UNETLoader registers Krea2 at job runtime so EmptyImage/boot stays clean.

FROM ghcr.io/turn594/pp-krea-worker:b5905da7fd0065041f59b69e6b7d2b795dcec3e8

USER root

COPY custom_nodes/pp_krea2/ /comfyui/custom_nodes/pp_krea2/

RUN test -f /comfyui/custom_nodes/pp_krea2/__init__.py \
  && test -f /comfyui/custom_nodes/pp_krea2/krea2_dit/model.py \
  && grep -q PPKrea2UNETLoader /comfyui/custom_nodes/pp_krea2/__init__.py \
  && echo pp_krea2_unet_node_ok
