"""
Vendored from OliverCrosby/ComfyUI-Universal-Seamless-Tiles (MIT)
https://github.com/OliverCrosby/ComfyUI-Universal-Seamless-Tiles

The architecture-correct DiT path for Krea (Wan VAE + transformer denoise):
  1) SeamlessTileModelDiT  — per-step latent ROLL tapered by sigma (not pad-expand)
  2) MakeCircularVAEDiT    — circular pad on Conv2d AND CausalConv3d (Wan/Krea VAE)

Why our pad/pad_blend/fixed-roll was wrong:
  - Expanding latent W each step fights DiT patch/pos layout → freckle scramble
  - Fixed shift every step lets the model lock a mid-frame "false seam"
  - Soft crop blend masks numbers but does not make the denoiser think periodically
  - Skipping circular VAE leaves pixel seams at decode (Krea uses Wan-family VAE)

Turbo note from upstream: latent rolling wants more steps (15–20) for tight seams.
"""

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
    """Deterministic per-step roll; same offset for cond+uncond within a step."""
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
        scale = (sigma / state["max_sigma"]) if state["max_sigma"] > 0 else 1.0

        height, width = inp.shape[-2], inp.shape[-1]
        dy, dx = _step_offsets(seed, timestep, height, width, tile_x, tile_y, scale)
        if dy == 0 and dx == 0:
            return apply_model(inp, timestep, **c)

        shifts = (dy, dx)
        dims = (-2, -1)
        rolled = torch.roll(inp, shifts=shifts, dims=dims)
        c_rolled = _roll_conds(c, shifts, dims)
        out = apply_model(rolled, timestep, **c_rolled)
        return torch.roll(out, shifts=(-dy, -dx), dims=dims)

    return wrapper


class SeamlessTileModelDiT:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "tiling": (TILING_MODES,),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "run"
    CATEGORY = "conditioning"

    def run(self, model, tiling, seed):
        m = model.clone()
        if tiling == "disable":
            return (m,)
        m.set_model_unet_function_wrapper(_make_tiling_wrapper(seed, tiling))
        print(f"[ust] SeamlessTileModelDiT tiling={tiling} seed={seed}")
        return (m,)


def _replacement_conv2d_forward(self, input: Tensor, weight: Tensor, bias):
    working = F.pad(input, self._tile_padX, mode=self._tile_modeX)
    working = F.pad(working, self._tile_padY, mode=self._tile_modeY)
    return F.conv2d(working, weight, bias, self.stride, _pair(0), self.dilation, self.groups)


def _patch_conv2d(layer, tile_x, tile_y):
    rp = layer._reversed_padding_repeated_twice
    layer._tile_modeX = "circular" if tile_x else "constant"
    layer._tile_modeY = "circular" if tile_y else "constant"
    layer._tile_padX = (rp[0], rp[1], 0, 0)
    layer._tile_padY = (0, 0, rp[2], rp[3])
    layer._conv_forward = _replacement_conv2d_forward.__get__(layer, layer.__class__)


def _replacement_conv3d_forward(self, input, weight, bias, autopad=None, *args, **kwargs):
    if self._tile_pw > 0:
        input = F.pad(input, (self._tile_pw, self._tile_pw, 0, 0, 0, 0), mode=self._tile_modeX)
    if self._tile_ph > 0:
        input = F.pad(input, (0, 0, self._tile_ph, self._tile_ph, 0, 0), mode=self._tile_modeY)
    if autopad is not None:
        return self._tile_orig_conv_forward(input, weight, bias, autopad=autopad, *args, **kwargs)
    return self._tile_orig_conv_forward(input, weight, bias, *args, **kwargs)


def _patch_conv3d(layer, tile_x, tile_y):
    if not getattr(layer, "_tile_wrapped", False):
        pd, ph, pw = _triple(layer.padding)
        if ph == 0 and pw == 0:
            return
        layer._tile_ph, layer._tile_pw = ph, pw
        layer._tile_orig_conv_forward = layer._conv_forward
        layer.padding = (pd, 0, 0)
        layer._conv_forward = _replacement_conv3d_forward.__get__(layer, layer.__class__)
        layer._tile_wrapped = True
    layer._tile_modeX = "circular" if tile_x else "constant"
    layer._tile_modeY = "circular" if tile_y else "constant"


def make_circular(module, tile_x, tile_y):
    for layer in module.modules():
        if isinstance(layer, torch.nn.Conv2d):
            _patch_conv2d(layer, tile_x, tile_y)
        elif isinstance(layer, torch.nn.Conv3d):
            _patch_conv3d(layer, tile_x, tile_y)
    return module


class MakeCircularVAEDiT:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "vae": ("VAE",),
                "tiling": (TILING_MODES,),
                "copy_vae": (["Make a copy", "Modify in place"],),
            },
        }

    RETURN_TYPES = ("VAE",)
    FUNCTION = "run"
    CATEGORY = "latent"

    def run(self, vae, tiling, copy_vae):
        if copy_vae == "Modify in place":
            vae_copy = vae
        else:
            try:
                vae_copy = copy.deepcopy(vae)
            except Exception as e:
                print(f"[ust] deepcopy vae failed ({e}); modify in place")
                vae_copy = vae

        tile_x, tile_y = _axes_for(tiling)
        # Comfy VAE object shapes differ by version / model family
        model = getattr(vae_copy, "first_stage_model", None)
        if model is None:
            model = getattr(vae_copy, "model", None)
        if model is None and hasattr(vae_copy, "patcher"):
            try:
                model = vae_copy.patcher.model
            except Exception:
                model = None
        if model is None:
            print(
                "[ust] MakeCircularVAEDiT: no nn module on VAE "
                f"(type={type(vae_copy).__name__}); skip circular patch"
            )
            return (vae_copy,)
        make_circular(model, tile_x, tile_y)
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
