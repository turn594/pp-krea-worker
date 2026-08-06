"""UST DiT wrap — soft import so node bugs do not kill worker boot."""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
try:
    from .comfy_universal_seamless import (
        NODE_CLASS_MAPPINGS as _M,
        NODE_DISPLAY_NAME_MAPPINGS as _D,
    )
    NODE_CLASS_MAPPINGS.update(_M)
    NODE_DISPLAY_NAME_MAPPINGS.update(_D)
    print("[ust] loaded comfy_universal_seamless")
except Exception as e:
    print("[ust] soft-fail import:", type(e).__name__, e)
