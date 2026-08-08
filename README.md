# Personal Paw — Krea worker (verified base)

**Rule:** official `worker-comfyui` is the fix; our custom boot is suspect until assign works.

Full write-up: [VERIFIED_BASE.md](./VERIFIED_BASE.md)

## Default image

```text
FROM runpod/worker-comfyui:5.8.6-base
+ Comfy core bump (krea2 TE)
+ custom_nodes: universal_seamless, pp_krea2
+ extra_model_paths (official keys + diffusion_models + text_encoders)
+ runpod>=1.10.1  (docs: volume job-tracking corruption in 1.7.11–1.10.0)
CMD ["/start.sh"]   ← stock dispatch only
```

## Why stock `/start.sh` by default

Verified (RunPod golden path): workers **ready** + jobs **IN_QUEUE** / **inProgress: 0** ⇒ image mis-dispatching — switch to known-good worker, don’t invent a new boot.

Our old `CMD ["/prewarm.sh"]` started Comfy ourselves and only then ran `/handler.py`, skipping the official lifecycle. That is now **legacy** (`/prewarm.sh` still in image for cold experiments **after** assign is green).

## Deploy checks (A0 before B)

| Step | What | Pass |
|------|------|------|
| **A0** | EmptyImage (or mini) on this image, min=0 | Job leaves IN_QUEUE when workers show ready; delayTime becomes real |
| **A** | Repeat assign after scale-to-zero | Stable |
| **B** | Product workflow cold | Only after A0/A |
| **C** | Idle past timeout | Workers count → 0 |

If A0 fails: set endpoint to pure `runpod/worker-comfyui:5.8.6-base` (no volume). If stock works and ours doesn’t → our layers; if stock fails → platform/ticket.

## Optional entrypoints (override CMD)

| CMD | Use |
|-----|-----|
| `/start.sh` | **Default** — verified |
| `/pp_flash_start.sh` | Hardlink hot weights then stock start |
| `/prewarm.sh` | Product VRAM prewarm then handler only — **B only**; can desync ready vs pull |

## Ladder (historical)

| Step | Image | Pass |
|------|--------|------|
| 1 | Stock `5.8.6-base` only | EmptyImage COMPLETED |
| 2 | + UST nodes | Mini + UST |
| 3 | + Comfy/krea2 | CLIP loads |
| 4 | + volume paths + product nodes | Product PNG |

Deploy: GitHub `turn594/pp-krea-worker` · volume only after A0 without volume is green (or product step explicitly).
