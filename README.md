# Personal Paw — RunPod Krea worker

Recipe for RunPod **Serverless** so collar art is generated with:

- Krea Turbo (models on your RunPod network volume)
- Wrap nodes (seamless tile on the collar band)

**Art still runs only on RunPod.** This repo is just the install recipe.

## Deploy (console)

1. RunPod → **Serverless** → **New Endpoint** → **Start from GitHub Repo**
2. Pick this repo
3. Dockerfile path: `Dockerfile` · context: `/`
4. Attach network volume **xf0nyvfim9** (region **US-IL-1**)
5. FlashBoot **ON** · workers min **0** · max **2** · idle **180s**
6. GPU: **24GB+** (A6000 / L40S / similar)

After the build finishes, copy the endpoint ID and use it for smoke / Cloudflare secrets.
