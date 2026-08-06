# Personal Paw — Krea worker (step ladder)

**Rule:** one change → fail-fast smoke (≤45s) → only then next step.

| Step | What’s in the image | Pass criteria |
|------|---------------------|---------------|
| **1** | Stock `worker-comfyui:5.8.6-base` only | Mini EmptyImage COMPLETED (warm preferred) |
| **2** | + soft UST custom nodes | Mini OK + UST node exists |
| **3** | + Comfy upgrade for `krea2` CLIP | Product CLIP loads / no type error |
| **4** | + volume models path | Full Krea+UST product PNG |

Deploy: RunPod Serverless → GitHub repo `turn594/pp-krea-worker` · volume `xf0nyvfim9` only after step 4.
