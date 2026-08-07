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

        # Prefer stock load_clip when core already has CLIPType.KREA2
        # (do NOT rebuild Enum with type() — that raises EnumType.__new__ missing classdict)
        if hasattr(sd.CLIPType, "KREA2"):
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

        # Direct TE construction (works without core KREA2 enum)
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

        te_cls = krea2.te(**te_kwargs) if te_kwargs else krea2.te()

        class _Tgt:
            pass

        tgt = _Tgt()
        # CLIP expects target.clip to be a class (callable), tokenizer class, params dict
        tgt.clip = te_cls
        tgt.tokenizer = krea2.Krea2Tokenizer
        tgt.params = {}

        # Critical: pass state_dict so TE weights actually load.
        # Without this, encode hits "'Linear' object has no attribute 'weight'".
        params_n = 0
        try:
            params_n = comfy.utils.calculate_parameters(state)
        except Exception:
            try:
                params_n = sum(int(v.numel()) for v in state.values() if hasattr(v, "numel"))
            except Exception:
                params_n = 0

        def _build(kwargs):
            return CLIP(tgt, **kwargs)

        attempts = [
            dict(
                embedding_directory=emb,
                model_options=model_options,
                state_dict=[state],
                parameters=params_n,
            ),
            dict(
                embedding_directory=emb,
                model_options=model_options,
                state_dict=state,
                parameters=params_n,
            ),
            dict(embedding_directory=emb, state_dict=[state]),
            dict(embedding_directory=emb, state_dict=state),
        ]
        last_err = None
        for kw in attempts:
            try:
                clip_obj = _build(kw)
                print("[pp_krea2] direct TE CLIP OK", list(kw.keys()))
                return (clip_obj,)
            except TypeError as e:
                last_err = e
                print("[pp_krea2] CLIP ctor TypeError", e, list(kw.keys()))
            except Exception as e:
                last_err = e
                print("[pp_krea2] CLIP ctor fail", type(e).__name__, e)
        raise RuntimeError(f"PPKrea2CLIPLoader: CLIP construct failed: {last_err}")


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
