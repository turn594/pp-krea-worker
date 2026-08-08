# Verified base (GitHub / RunPod docs = fix; our fork = suspect)

## Problem class (freelancer signal, restated)

Console/health can show workers **ready** / non-zero while jobs sit **IN_QUEUE** with **inProgress: 0**, or other signals that **do not correspond**. If zero/ready/queue disagree, cold-path work and “return to zero” checks are meaningless until dispatch is honest.

## Verified sources (treat as authority)

### 1. Ready + IN_QUEUE / inProgress: 0 → broken image, switch workers

RunPod golden path (live-verified 2026-07):

> When a Hub worker's workers go `ready` but jobs sit `IN_QUEUE` with `inProgress: 0`, that worker image is broken/mis-dispatching — **switch workers, don't wait it out.**

Source:  
https://github.com/runpod/runpod-plugins-official/blob/main/plugins/runpod/skills/runpod/golden-paths/03-whisper-endpoint/variant-a-hub.md

**Implication for us:** Custom CMD that reimplements Comfy+handler (`prewarm.sh` → start Comfy → wait → only `/handler.py`) is **not** the verified dispatch path. Stock is `/start.sh` (Comfy + handler together, official GPU preflight).

### 2. Network volume + bad runpod SDK → jobs stuck while workers look free

RunPod docs — *Jobs funneled to a single worker* / queue while workers available:

- Affected: Runpod Python SDK **1.7.11–1.10.0** (also cited as 1.9.1–1.10.0 in older notes)
- Especially **network volume** endpoints (Comfy workers called out)
- Corrupts per-worker job tracking → workers stop pulling
- **Fix:** `pip install --upgrade "runpod>=1.10.1"`, **rebuild and redeploy image**

Source: https://docs.runpod.io/serverless/troubleshooting

### 3. Official worker lifecycle

Repo: https://github.com/runpod-workers/worker-comfyui  
Image: `runpod/worker-comfyui:5.8.6-base` (latest release tag as of this write-up)

- `/start.sh`: GPU kernel preflight → Comfy → `/handler.py`
- Volume: `/runpod-volume` + `extra_model_paths.yaml`
- `NETWORK_VOLUME_DEBUG=true` for path diagnostics
- Stock does **not** product-prewarm VRAM (cold B is separate from A)

### 4. What we do **not** treat as verified

- Random Hub workers that show ready but never consume queue (golden path: switch away)
- Replacing `/start.sh` with a full custom boot unless proven on empty/stock first
- Assuming prewarm-before-handler “ready means hot” fixes assign (can make ready/queue **less** aligned)

## Ours = broken until proven

| Our choice | Risk vs verified |
|---|---|
| `CMD ["/prewarm.sh"]` (custom Comfy then handler only) | Diverges from stock dispatch; delay before handler polls |
| Surgical GHCR base layers | Harder to prove vs `runpod/worker-comfyui:5.8.6-base` |
| Product prewarm before handler | B optimization; must not block A |

## Build strategy: verified first, product second

1. **Image A (assign probe):** `Dockerfile` → FROM official base + nodes + paths + `runpod>=1.10.1` + **stock `/start.sh` only**  
2. **Image B (cold later):** same + optional prewarm **only after** Image A assigns cleanly  
3. **Endpoint:** min=0, FlashBoot on, volume only when testing product; first prove EmptyImage on stock path  
4. **A0 check every deploy:** health workers ready vs job inProgress / delayTime — if ready and inProgress=0 forever → image/config bad, switch back to stock  

## Acceptance (three separate)

| ID | Check |
|---|---|
| **A0** | Signals agree: job leaves IN_QUEUE when workers ready (stock EmptyImage) |
| **A** | min=0 assign works repeatedly |
| **B** | True cold product timing after real scale-to-zero |
| **C** | After idle, workers count returns to 0 |

Do not optimize B until A0/A pass on **verified** entrypoint.
