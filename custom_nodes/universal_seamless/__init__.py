"""
Vendored UST DiT wrap nodes for Personal Paw (Krea collar seamless).
Import is soft-fail so a node bug cannot kill the whole worker boot
(RunPod AI + community: custom_nodes import crash => worker EXIT).
"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    import copy
    import torch
    from torch import Tensor
    from torch.nn import functional as F
    from torch.nn.modules.utils import _pair, _triple

    TILING_MODES = ["enable", "x_only", "y_only", "disable"]

    def _axes_for(tiling):
        return (
            tiling in ("enable", "x_only"),
            tiling in ("enable", "y_only"),
        )

    def _step_offsets(seed, timestep, height, width, tile_x, tile_y, scale=1.0):
        try:
            t_val = float(timestep.flatten()[0].item())
        except Exception:
            t_val = 0.0
        key = (int(seed) & 0x7FFFFFFF) ^ (int(t_val * 100000.0) & 0x7FFFFFFF)
        gen = torch.Generator().manual_seed(int(key))
        dy = (
            int(round(scale * torch.randint(0, max(1, height), (1,), generator=gen).item()))
            if tile_y
            else 0
        )
        dx = (
            int(round(scale * torch.randint(0, max(1, width), (1,), generator=gen).item()))
            if tile_x
            else 0
        )
        return dy, dx

    def _roll_conds(c, shifts, dims):
        cc = c.get("c_concat", None)
        if cc is None or not torch.is_tensor(cc):
            return c
        new_c = dict(c)
        new_c["c_concat"] = torch.roll(cc, shifts=shifts, dims=dims)
        return new_c

    def _make_tiling_wrapper(seed, tiling):
        tile_x, tile_y = _axes_for(tiling)
        state = {"max_sigma": 0.0}

        def wrapper(apply_model, params):
            inp = params["input"]
            timestep = params["timestep"]
            c = params["c"]
            if not (tile_x or tile_y):
                return apply_model(inp, timestep, **c)
            try:
                sigma = float(timestep.flatten().max().item())
            except Exception:
                sigma = 0.0
            if sigma > state["max_sigma"]:
                state["max_sigma"] = sigma
            max_s = max(state["max_sigma"], 1e-6)
            scale = min(1.0, sigma / max_s)
            h, w = int(inp.shape[-2]), int(inp.shape[-1])
            dy, dx = _step_offsets(seed, timestep, h, w, tile_x, tile_y, scale)
            if dy == 0 and dx == 0:
                return apply_model(inp, timestep, **c)
            dims = []
            shifts = []
            if tile_y:
                dims.append(-2)
                shifts.append(dy)
            if tile_x:
                dims.append(-1)
                shifts.append(dx)
            rolled = torch.roll(inp, shifts=shifts, dims=dims)
            c2 = _roll_conds(c, shifts=shifts, dims=dims)
            out = apply_model(rolled, timestep, **c2)
            return torch.roll(out, shifts=[-s for s in shifts], dims=dims)

        return wrapper

    def make_circular(model, tile_x=True, tile_y=True):
        for m in model.modules():
            if isinstance(m, torch.nn.Conv2d):
                m.padding_mode = "circular"
                # keep padding sizes
            # CausalConv3d-like modules often subclass Conv3d
            if isinstance(m, torch.nn.Conv3d):
                try:
                    m.padding_mode = "circular"
                except Exception:
                    pass

    class SeamlessTileModelDiT:
        @classmethod
        def INPUT_TYPES(s):
            return {
                "required": {
                    "model": ("MODEL",),
                    "tiling": (TILING_MODES,),
                    "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                }
            }

        RETURN_TYPES = ("MODEL",)
        FUNCTION = "run"
        CATEGORY = "model"

        def run(self, model, tiling, seed):
            m = model.clone()
            m.set_model_unet_function_wrapper(_make_tiling_wrapper(seed, tiling))
            print(f"[ust] SeamlessTileModelDiT tiling={tiling} seed={seed}")
            return (m,)

    class MakeCircularVAEDiT:
        @classmethod
        def INPUT_TYPES(s):
            return {
                "required": {
                    "vae": ("VAE",),
                    "tiling": (TILING_MODES,),
                    "copy_vae": (["Make a copy", "Modify in place"],),
                }
            }

        RETURN_TYPES = ("VAE",)
        FUNCTION = "run"
        CATEGORY = "latent"

        def run(self, vae, tiling, copy_vae):
            if copy_vae == "Modify in place":
                vae_copy = vae
            else:
                vae_copy = copy.deepcopy(vae)
            tile_x, tile_y = _axes_for(tiling)
            make_circular(vae_copy.first_stage_model, tile_x, tile_y)
            print(f"[ust] MakeCircularVAEDiT tiling={tiling}")
            return (vae_copy,)

    NODE_CLASS_MAPPINGS = {
        "SeamlessTileModelDiT": SeamlessTileModelDiT,
        "MakeCircularVAEDiT": MakeCircularVAEDiT,
    }
    NODE_DISPLAY_NAME_MAPPINGS = {
        "SeamlessTileModelDiT": "Seamless Tile Model (DiT)",
        "MakeCircularVAEDiT": "Make Circular VAE (DiT)",
    }
    print("[ust] universal_seamless nodes loaded")
except Exception as e:
    print(f"[ust] WARN failed to load nodes (worker continues): {e!r}")
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
