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
        # try common locations (RunPod image, Modal /root/ComfyUI, cwd)
        for cand in (
            "/comfyui/comfy/text_encoders",
            "/root/ComfyUI/comfy/text_encoders",
            os.path.join(os.getcwd(), "comfy", "text_encoders"),
            os.path.join(os.getcwd(), "ComfyUI", "comfy", "text_encoders"),
        ):
            if os.path.isdir(cand):
                te_dir = cand
                break
    if not te_dir:
        # last resort: import comfy package file location
        try:
            import comfy

            base = os.path.dirname(getattr(comfy, "__file__", "") or "")
            cand = os.path.join(base, "text_encoders")
            if os.path.isdir(cand):
                te_dir = cand
        except Exception:
            pass
    if not te_dir:
        raise RuntimeError("cannot locate comfy/text_encoders directory")

    node_dir = os.path.dirname(__file__)
    # Install krea2 TE + deps that older ComfyUI trees lack.
    # Order: leaf deps first, then qwen3vl, then krea2 (imports qwen3vl).
    copies = [
        ("llama.py", "llama.py"),
        ("qwen_image.py", "qwen_image.py"),
        ("hunyuan_video.py", "hunyuan_video.py"),
        ("qwen3vl.py", "qwen3vl.py"),
        ("krea2_te.py", "krea2.py"),
    ]
    for src_name, dst_name in copies:
        s = os.path.join(node_dir, src_name)
        d = os.path.join(te_dir, dst_name)
        if os.path.isfile(s):
            try:
                shutil.copy2(s, d)
                print("[pp_krea2] installed", d)
            except Exception as e:
                print("[pp_krea2] copy", src_name, e)

    importlib.invalidate_caches()
    # Force reimport
    import sys

    for mod in (
        "comfy.text_encoders.krea2",
        "comfy.text_encoders.qwen3vl",
        "comfy.text_encoders.llama",
        "comfy.text_encoders.qwen_image",
        "comfy.text_encoders.hunyuan_video",
    ):
        sys.modules.pop(mod, None)
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


def _ensure_krea2_unet_runtime():
    """Runtime-only registration so boot is never broken by core file edits.

    Patches detect_unet_config + registers Krea2 in model_base/supported_models
    and installs vendored SingleStreamDiT as comfy.ldm.krea2.model.
    """
    import importlib
    import importlib.util
    import sys
    import types

    import torch
    import comfy.model_base as model_base
    import comfy.model_detection as model_detection
    import comfy.supported_models as supported_models
    import comfy.supported_models_base as supported_models_base
    import comfy.latent_formats as latent_formats

    if getattr(model_detection, "_pp_krea2_unet", False):
        print("[pp_krea2] unet runtime already patched")
        return

    # --- install vendored DiT as comfy.ldm.krea2.model ---
    dit_dir = os.path.join(os.path.dirname(__file__), "krea2_dit")
    model_py = os.path.join(dit_dir, "model.py")
    if not os.path.isfile(model_py):
        raise FileNotFoundError("missing vendored krea2_dit/model.py")

    # package parents
    if "comfy.ldm.krea2" not in sys.modules:
        pkg = types.ModuleType("comfy.ldm.krea2")
        pkg.__path__ = [dit_dir]
        sys.modules["comfy.ldm.krea2"] = pkg
    if "comfy.ldm.krea2.model" not in sys.modules:
        spec = importlib.util.spec_from_file_location("comfy.ldm.krea2.model", model_py)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["comfy.ldm.krea2.model"] = mod
        spec.loader.exec_module(mod)
        print("[pp_krea2] loaded vendored SingleStreamDiT")

    # --- model_base.Krea2 ---
    if not hasattr(model_base, "Krea2"):
        import comfy.conds

        class Krea2(model_base.BaseModel):
            def __init__(self, model_config, model_type=model_base.ModelType.FLUX, device=None):
                super().__init__(
                    model_config,
                    model_type,
                    device=device,
                    unet_model=sys.modules["comfy.ldm.krea2.model"].SingleStreamDiT,
                )
                self.memory_usage_factor_conds = ("ref_latents",)

            def extra_conds(self, **kwargs):
                out = super().extra_conds(**kwargs)
                cross_attn = kwargs.get("cross_attn", None)
                if cross_attn is not None:
                    out["c_crossattn"] = comfy.conds.CONDRegular(cross_attn)
                ref_latents = kwargs.get("reference_latents", None)
                if ref_latents is not None:
                    latents = [self.process_latent_in(lat) for lat in ref_latents]
                    out["ref_latents"] = comfy.conds.CONDList(latents)
                attention_mask = kwargs.get("attention_mask", None)
                if attention_mask is not None:
                    out["attention_mask"] = comfy.conds.CONDRegular(attention_mask)
                return out

        model_base.Krea2 = Krea2
        print("[pp_krea2] registered model_base.Krea2")

    # --- supported_models.Krea2 ---
    if not hasattr(supported_models, "Krea2"):
        try:
            lf = latent_formats.Wan21
        except Exception:
            try:
                lf = latent_formats.Flux
            except Exception:
                lf = latent_formats.SD15

        class Krea2SM(supported_models_base.BASE):
            unet_config = {"image_model": "krea2"}
            sampling_settings = {"multiplier": 1.0, "shift": 1.15}
            memory_usage_factor = 2.2
            latent_format = lf
            supported_inference_dtypes = [torch.bfloat16, torch.float16, torch.float32]
            vae_key_prefix = ["vae."]
            text_encoder_key_prefix = ["text_encoders."]

            def get_model(self, state_dict, prefix="", device=None):
                return model_base.Krea2(self, device=device)

            def clip_target(self, state_dict={}):
                _ensure_krea2_module()
                import comfy.text_encoders.krea2 as krea2

                return supported_models_base.ClipTarget(krea2.Krea2Tokenizer, krea2.te())

        supported_models.Krea2 = Krea2SM
        models = getattr(supported_models, "models", None)
        if isinstance(models, list) and Krea2SM not in models:
            models.insert(0, Krea2SM)
            print("[pp_krea2] inserted Krea2 into supported_models.models")
        print("[pp_krea2] registered supported_models.Krea2")

    # --- patch detect_unet_config ---
    _orig_detect = model_detection.detect_unet_config

    def _detect_unet_config(state_dict, key_prefix, metadata=None):
        keys = state_dict.keys() if hasattr(state_dict, "keys") else state_dict
        probe = "{}txtfusion.projector.weight".format(key_prefix)
        if probe in keys or any(str(k).endswith("txtfusion.projector.weight") for k in keys):
            # minimal config — matches() only needs image_model == krea2
            print("[pp_krea2] detect_unet_config -> krea2")
            return {"image_model": "krea2"}
        # some calls use keyword-only metadata on older/newer signatures
        try:
            return _orig_detect(state_dict, key_prefix, metadata=metadata)
        except TypeError:
            return _orig_detect(state_dict, key_prefix)

    model_detection.detect_unet_config = _detect_unet_config
    model_detection._pp_krea2_unet = True
    print("[pp_krea2] unet runtime patch ready")


class PPKrea2UNETLoader:
    """Load Krea2 Turbo UNET when stock UNETLoader cannot detect model type."""

    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths

        names = []
        for folder in ("diffusion_models", "unet"):
            try:
                names.extend(folder_paths.get_filename_list(folder) or [])
            except Exception:
                pass
        # de-dupe preserve order
        seen = set()
        uniq = []
        for n in names:
            if n not in seen:
                seen.add(n)
                uniq.append(n)
        if not uniq:
            uniq = ["krea2_turbo_fp8_scaled.safetensors"]
        return {
            "required": {
                "unet_name": (uniq,),
                "weight_dtype": (["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"],),
            }
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "load_unet"
    CATEGORY = "model/loaders"
    DESCRIPTION = "Krea2 Turbo UNET loader (Personal Paw)"

    def load_unet(self, unet_name, weight_dtype="default"):
        import torch
        import folder_paths
        import comfy.sd as sd

        print("[pp_krea2] UNET load start", unet_name, weight_dtype)
        _ensure_krea2_unet_runtime()

        model_options = {}
        if weight_dtype == "fp8_e4m3fn":
            model_options["dtype"] = torch.float8_e4m3fn
        elif weight_dtype == "fp8_e4m3fn_fast":
            model_options["dtype"] = torch.float8_e4m3fn
            model_options["fp8_optimizations"] = True
        elif weight_dtype == "fp8_e5m2":
            model_options["dtype"] = torch.float8_e5m2

        unet_path = None
        for folder in ("diffusion_models", "unet"):
            try:
                if hasattr(folder_paths, "get_full_path_or_raise"):
                    try:
                        unet_path = folder_paths.get_full_path_or_raise(folder, unet_name)
                    except Exception:
                        unet_path = folder_paths.get_full_path(folder, unet_name)
                else:
                    unet_path = folder_paths.get_full_path(folder, unet_name)
            except Exception:
                unet_path = None
            if unet_path:
                break
        if not unet_path:
            for p in (
                f"/runpod-volume/models/diffusion_models/{unet_name}",
                f"/runpod-volume/models/unet/{unet_name}",
                f"/comfyui/models/diffusion_models/{unet_name}",
            ):
                if os.path.isfile(p):
                    unet_path = p
                    break
        if not unet_path:
            raise FileNotFoundError(f"PPKrea2UNETLoader: missing {unet_name}")

        print("[pp_krea2] UNET path", unet_path)
        model = sd.load_diffusion_model(unet_path, model_options=model_options)
        if model is None:
            raise RuntimeError("load_diffusion_model returned None for Krea2 weights")
        print("[pp_krea2] UNET load OK")
        return (model,)


NODE_CLASS_MAPPINGS = {
    "PPKrea2CLIPLoader": PPKrea2CLIPLoader,
    "CLIPLoaderKrea2": PPKrea2CLIPLoader,
    "PPKrea2UNETLoader": PPKrea2UNETLoader,
    "UNETLoaderKrea2": PPKrea2UNETLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PPKrea2CLIPLoader": "CLIP Loader (Krea2)",
    "CLIPLoaderKrea2": "CLIP Loader (Krea2 alias)",
    "PPKrea2UNETLoader": "UNET Loader (Krea2)",
    "UNETLoaderKrea2": "UNET Loader (Krea2 alias)",
}

print("[pp_krea2] registered CLIP+UNET Krea2 loaders")
