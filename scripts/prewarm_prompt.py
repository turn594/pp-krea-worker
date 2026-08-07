#!/usr/bin/env python3
"""Submit tiny workflow that loads the same models product uses (PPKrea2 + VAE + 1 step)."""
import json
import time
import urllib.request

PORT = 8188
BASE = f"http://127.0.0.1:{PORT}"

# Match customer product path (PPKrea2 + UST seamless) so first job does not re-wrap models.
# Tiny spatial size + 1 step — forces weight load + UST paths into VRAM before ready.
WORKFLOW = {
    "1": {
        "class_type": "PPKrea2UNETLoader",
        "inputs": {
            "unet_name": "krea2_turbo_fp8_scaled.safetensors",
            "weight_dtype": "default",
        },
    },
    "2": {
        "class_type": "PPKrea2CLIPLoader",
        "inputs": {
            "clip_name": "qwen3vl_4b_fp8_scaled.safetensors",
            "device": "default",
        },
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "qwen_image_vae.safetensors"},
    },
    "3b": {
        "class_type": "MakeCircularVAEDiT",
        "inputs": {"vae": ["3", 0], "tiling": "x_only", "copy_vae": "Make a copy"},
    },
    "4": {
        "class_type": "SeamlessTileModelDiT",
        "inputs": {"model": ["1", 0], "tiling": "x_only", "seed": 1},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["2", 0], "text": "prewarm seamless collar"},
    },
    "7a": {
        "class_type": "ConditioningZeroOut",
        "inputs": {"conditioning": ["6", 0]},
    },
    "8": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {"width": 512, "height": 256, "batch_size": 1},
    },
    "9": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7a", 0],
            "latent_image": ["8", 0],
            "seed": 1,
            "steps": 1,
            "cfg": 1,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1,
        },
    },
    "10": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["9", 0], "vae": ["3b", 0]},
    },
    "11": {
        "class_type": "SaveImage",
        "inputs": {"images": ["10", 0], "filename_prefix": "prewarm"},
    },
}


def post(path, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    # ComfyUI prompt API
    body = {"prompt": WORKFLOW, "client_id": "pp-prewarm"}
    try:
        res = post("/prompt", body)
    except Exception as e:
        # Some builds use different route
        print("[prewarm_prompt] /prompt failed", e)
        raise
    pid = res.get("prompt_id")
    print("[prewarm_prompt] prompt_id", pid)
    t0 = time.time()
    while time.time() - t0 < 180:
        try:
            hist = get(f"/history/{pid}")
            if pid in hist:
                print("[prewarm_prompt] completed", hist[pid].get("status"))
                return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("prewarm timeout")


if __name__ == "__main__":
    main()
