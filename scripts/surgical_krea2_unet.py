#!/usr/bin/env python3
"""Add Krea2 UNET support without replacing whole model_base/supported_models.

Full file replace from master breaks boot on older worker-comfyui cores.
Only: copy ldm/krea2, inject detect branch, append classes if missing.
"""
from __future__ import annotations

import os
import re
import tarfile
import urllib.request

COMFY = "/comfyui/comfy"
TGZ = "/tmp/comfy_krea_unet.tgz"
URL = "https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz"

DETECT_SNIPPET = '''
    if '{}txtfusion.projector.weight'.format(key_prefix) in state_dict_keys:  # Krea 2 (K2) pp-surgical
        dit_config = {}
        dit_config["image_model"] = "krea2"
        head_dim = 128
        first_w = state_dict['{}first.weight'.format(key_prefix)]
        dit_config["features"] = first_w.shape[0]
        dit_config["channels"] = first_w.shape[1]
        # patch size often 2 for DiT
        dit_config["patch_size"] = 2
        dit_config["axes_dim"] = [16, 56, 56]
        dit_config["theta"] = 10000
        dit_config["num_heads"] = dit_config["features"] // head_dim if head_dim else 24
        return dit_config
'''

MODEL_BASE_SNIPPET = '''

# --- pp surgical Krea2 ---
class Krea2(BaseModel):
    def __init__(self, model_config, model_type=ModelType.FLUX, device=None):
        super().__init__(model_config, model_type, device=device, unet_model=comfy.ldm.krea2.model.SingleStreamDiT)
        self.memory_usage_factor_conds = ("ref_latents",)

    def extra_conds(self, **kwargs):
        out = super().extra_conds(**kwargs)
        cross_attn = kwargs.get("cross_attn", None)
        if cross_attn is not None:
            out["c_crossattn"] = comfy.conds.CONDRegular(cross_attn)
        ref_latents = kwargs.get("reference_latents", None)
        if ref_latents is not None:
            latents = []
            for lat in ref_latents:
                latents.append(self.process_latent_in(lat))
            out["ref_latents"] = comfy.conds.CONDList(latents)
        attention_mask = kwargs.get("attention_mask", None)
        if attention_mask is not None:
            out["attention_mask"] = comfy.conds.CONDRegular(attention_mask)
        return out
'''

SUPPORTED_SNIPPET = '''

# --- pp surgical Krea2 ---
class Krea2(supported_models_base.BASE):
    unet_config = {"image_model": "krea2"}
    sampling_settings = {"multiplier": 1.0, "shift": 1.15}
    memory_usage_factor = 2.2
    try:
        latent_format = latent_formats.Wan21
    except Exception:
        latent_format = latent_formats.SD15
    supported_inference_dtypes = [torch.bfloat16, torch.float16, torch.float32]
    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Krea2(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(
            comfy.text_encoders.krea2.Krea2Tokenizer,
            comfy.text_encoders.krea2.te(),
        )
'''


def install_ldm_krea2() -> None:
    print("download", URL)
    urllib.request.urlretrieve(URL, TGZ)
    with tarfile.open(TGZ, "r:gz") as tf:
        members = [m for m in tf.getmembers() if "/comfy/ldm/krea2/" in m.name and not m.isdir()]
        if not members:
            raise RuntimeError("no ldm/krea2 in tarball")
        dest_root = os.path.join(COMFY, "ldm", "krea2")
        os.makedirs(dest_root, exist_ok=True)
        for m in members:
            rel = m.name.split("/comfy/ldm/krea2/", 1)[1]
            out = os.path.join(dest_root, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            src = tf.extractfile(m)
            with open(out, "wb") as f:
                f.write(src.read())
            print("ldm/krea2", rel)
    # ensure package init
    init = os.path.join(COMFY, "ldm", "krea2", "__init__.py")
    if not os.path.isfile(init):
        open(init, "w").write("# pp surgical\n")
    try:
        os.remove(TGZ)
    except OSError:
        pass


def patch_detection() -> None:
    path = os.path.join(COMFY, "model_detection.py")
    t = open(path, encoding="utf-8", errors="replace").read()
    if "image_model\"] = \"krea2\"" in t or "image_model'] = 'krea2'" in t or 'image_model"] = "krea2"' in t:
        print("model_detection already has krea2")
        return
    if "txtfusion.projector.weight" in t and "krea2" in t:
        print("model_detection already krea2-ish")
        return
    # insert before a common return dit_config near flux-like blocks
    anchor = "return dit_config"
    idx = t.rfind(anchor)
    if idx < 0:
        # append function is hard; inject near end of unet_config_from_diffusers_unet or similar
        print("WARN: no return dit_config anchor; appending detect helper")
        t = t + "\n# pp krea2 detect missing proper anchor\n"
        open(path, "w", encoding="utf-8").write(t)
        return
    # find start of that return's block - insert BEFORE last return dit_config in detect function
    # Safer: insert after first "def unet_config_from_diffusers_unet" body start... 
    # Insert right before the last occurrence of "return dit_config" that is indented
    t2 = t[:idx] + DETECT_SNIPPET + "\n    " + t[idx:]
    open(path, "w", encoding="utf-8").write(t2)
    print("model_detection: injected krea2 branch")


def patch_model_base() -> None:
    path = os.path.join(COMFY, "model_base.py")
    t = open(path, encoding="utf-8", errors="replace").read()
    if re.search(r"class Krea2\b", t):
        print("model_base already has Krea2")
        return
    # ensure import for ldm.krea2 path exists via full module path in snippet
    if "import comfy.ldm" not in t and "comfy.ldm" not in t:
        t = "import comfy.ldm.krea2.model  # pp surgical\n" + t
    open(path, "w", encoding="utf-8").write(t + MODEL_BASE_SNIPPET)
    print("model_base: appended Krea2")


def patch_supported() -> None:
    path = os.path.join(COMFY, "supported_models.py")
    t = open(path, encoding="utf-8", errors="replace").read()
    if re.search(r"class Krea2\b", t):
        print("supported_models already has Krea2")
    else:
        # ensure imports
        if "import comfy.text_encoders.krea2" not in t:
            t = t.replace(
                "import comfy.text_encoders",
                "import comfy.text_encoders\nimport comfy.text_encoders.krea2  # pp",
                1,
            )
        t = t + SUPPORTED_SNIPPET
        print("supported_models: appended Krea2 class")
    # register in models list if present
    if re.search(r"models\s*=\s*\[", t) and "Krea2" not in re.search(r"models\s*=\s*\[[\s\S]*?\]", t).group(0) if re.search(r"models\s*=\s*\[[\s\S]*?\]", t) else True:
        t2, n = re.subn(
            r"(models\s*=\s*\[)",
            r"\1\n    Krea2,",
            t,
            count=1,
        )
        if n:
            t = t2
            print("supported_models: registered Krea2 in models list")
        else:
            # try models.append style
            if "models =" in t and "Krea2," not in t:
                t = t.replace("models = [", "models = [\n    Krea2,", 1)
                print("supported_models: forced models list insert")
    open(path, "w", encoding="utf-8").write(t)


def main() -> None:
    assert os.path.isdir(COMFY), COMFY
    install_ldm_krea2()
    patch_detection()
    patch_model_base()
    patch_supported()
    assert os.path.isfile(os.path.join(COMFY, "ldm", "krea2", "model.py"))
    print("surgical_krea2_unet_ok")


if __name__ == "__main__":
    main()
