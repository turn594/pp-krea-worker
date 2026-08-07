"""
PPKrea2CLIPLoader — load qwen3vl Krea2 TE without core Comfy having CLIP type krea2.

Installs vendored krea2_te.py into comfy.text_encoders, then loads via the same
weight path as upstream CLIPType.KREA2 (when available) or a direct TE build.
"""

from __future__ import annotations

import os
import shutil


def _ensure_krea2_module():
    import importlib
    import comfy.text_encoders as te_pkg

    # comfy.__file__ can be None (namespace); use text_encoders package path
    te_dir = os.path.dirname(getattr(te_pkg, "__file__", "") or "") or None
    src = os.path.join(os.path.dirname(__file__), "krea2_te.py")
    if not te_dir or not os.path.isdir(te_dir):
        # try common locations
        for cand in (
            "/comfyui/comfy/text_encoders",
            os.path.join(os.getcwd(), "comfy", "text_encoders"),
        ):
            if os.path.isdir(cand):
                te_dir = cand
                break
    if not te_dir:
        raise RuntimeError("cannot locate comfy/text_encoders directory")

    dst = os.path.join(te_dir, "krea2.py")
    if os.path.isfile(src):
        try:
            shutil.copy2(src, dst)
            print("[pp_krea2] installed", dst)
        except Exception as e:
            print("[pp_krea2] copy", e)

    importlib.invalidate_caches()
    # Force reimport
    import sys

    sys.modules.pop("comfy.text_encoders.krea2", None)
    import comfy.text_encoders.krea2 as krea2  # noqa: F401

    print("[pp_krea2] module OK", getattr(krea2, "__file__", "?"))
    return krea2


class PPKrea2CLIPLoader:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths

        return {
            "required": {
                "clip_name": (folder_paths.get_filename_list("text_encoders"),),
            },
            "optional": {
                "device": (["default", "cpu"], {"advanced": True}),
            },
        }

    RETURN_TYPES = ("CLIP",)
    FUNCTION = "load"
    CATEGORY = "loaders"
    DESCRIPTION = "Krea2 Qwen3-VL-4B CLIP loader (Personal Paw)"

    def load(self, clip_name, device="default"):
        import folder_paths
        import torch
        import comfy.sd as sd
        import comfy.utils

        print("[pp_krea2] load start", clip_name, device)
        krea2 = _ensure_krea2_module()

        model_options = {}
        if device == "cpu":
            model_options["load_device"] = model_options["offload_device"] = torch.device("cpu")

        # Resolve clip weights: text_encoders first, then clip (volume layout)
        clip_path = None
        for folder in ("text_encoders", "clip"):
            try:
                if hasattr(folder_paths, "get_full_path_or_raise"):
                    try:
                        clip_path = folder_paths.get_full_path_or_raise(folder, clip_name)
                    except Exception:
                        clip_path = folder_paths.get_full_path(folder, clip_name)
                else:
                    clip_path = folder_paths.get_full_path(folder, clip_name)
            except Exception as e:
                print("[pp_krea2] resolve", folder, e)
                clip_path = None
            if clip_path:
                print("[pp_krea2] resolved", folder, clip_path)
                break
        if not clip_path:
            # last resort: scan volume paths
            for p in (
                f"/runpod-volume/models/text_encoders/{clip_name}",
                f"/runpod-volume/models/clip/{clip_name}",
                f"/comfyui/models/text_encoders/{clip_name}",
            ):
                if os.path.isfile(p):
                    clip_path = p
                    print("[pp_krea2] fallback path", p)
                    break
        if not clip_path or not isinstance(clip_path, (str, bytes, os.PathLike)):
            raise FileNotFoundError(
                f"PPKrea2CLIPLoader: could not resolve clip file {clip_name!r}"
            )

        emb = None
        try:
            emb_list = folder_paths.get_folder_paths("embeddings")
            if emb_list:
                emb = emb_list
        except Exception:
            emb = None

        # Ensure CLIPType.KREA2 exists
        if not hasattr(sd.CLIPType, "KREA2"):
            members = {m.name: m.value for m in sd.CLIPType}
            members["KREA2"] = max(members.values()) + 1
            sd.CLIPType = type(sd.CLIPType)("CLIPType", members)
            print("[pp_krea2] added CLIPType.KREA2", members["KREA2"])

        # Prefer native load if core understands KREA2 fully
        try:
            clip = sd.load_clip(
                ckpt_paths=[clip_path],
                embedding_directory=emb,
                clip_type=sd.CLIPType.KREA2,
                model_options=model_options,
            )
            print("[pp_krea2] load_clip OK")
            return (clip,)
        except Exception as e:
            print("[pp_krea2] load_clip failed, trying direct TE:", e)

        # Direct TE construction
        from comfy.sd import CLIP

        state, metadata = comfy.utils.load_torch_file(
            clip_path, safe_load=True, return_metadata=True
        )
        try:
            state = comfy.utils.state_dict_prefix_replace(
                state,
                {
                    "model.language_model.": "model.",
                    "model.visual.": "visual.",
                    "lm_head.": "model.lm_head.",
                },
            )
        except Exception as e:
            print("[pp_krea2] prefix replace skip", e)

        te_kwargs = {}
        if hasattr(sd, "llama_detect"):
            try:
                te_kwargs = sd.llama_detect([state])
            except Exception as e:
                print("[pp_krea2] llama_detect", e)

        te = krea2.te(**te_kwargs) if te_kwargs else krea2.te()
        # SDXLClipModel-like objects often use load_sd
        if hasattr(te, "load_sd"):
            te.load_sd(state)
        elif hasattr(te, "load_state_dict"):
            te.load_state_dict(state, strict=False)
        else:
            raise RuntimeError("TE has no load_sd/load_state_dict")

        class _Tgt:
            pass

        tgt = _Tgt()
        tgt.clip = te
        tgt.tokenizer = krea2.Krea2Tokenizer
        # embedding_directory must be list or None, never [None]
        try:
            clip_obj = CLIP(tgt, embedding_directory=emb, model_options=model_options)
        except TypeError:
            try:
                clip_obj = CLIP(tgt, embedding_directory=emb)
            except TypeError:
                clip_obj = CLIP(tgt)
        print("[pp_krea2] direct TE CLIP OK")
        return (clip_obj,)


NODE_CLASS_MAPPINGS = {
    "PPKrea2CLIPLoader": PPKrea2CLIPLoader,
    # Alias so API workflows can use same name as stock if desired
    "CLIPLoaderKrea2": PPKrea2CLIPLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PPKrea2CLIPLoader": "CLIP Loader (Krea2)",
    "CLIPLoaderKrea2": "CLIP Loader (Krea2 alias)",
}

print("[pp_krea2] registered PPKrea2CLIPLoader")
