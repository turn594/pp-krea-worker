# FROM booting surgical image. Do NOT replace model_base.py wholesale (broke boot).
# Only: ldm/krea2 + inject/append Krea2 detection classes.

FROM ghcr.io/turn594/pp-krea-worker:b5905da7fd0065041f59b69e6b7d2b795dcec3e8

USER root
ENV PATH="/opt/venv/bin:${PATH}"

COPY scripts/surgical_krea2_unet.py /tmp/surgical_krea2_unet.py
RUN python /tmp/surgical_krea2_unet.py \
  && rm -f /tmp/surgical_krea2_unet.py \
  && test -f /comfyui/comfy/ldm/krea2/model.py \
  && grep -q krea2 /comfyui/comfy/model_detection.py \
  && grep -q 'class Krea2' /comfyui/comfy/model_base.py \
  && grep -q 'class Krea2' /comfyui/comfy/supported_models.py \
  && echo krea2_unet_append_ok
