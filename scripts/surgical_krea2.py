#!/usr/bin/env python3
"""Surgical krea2 support without full Comfy overlay.

Full /comfyui/comfy replace breaks /opt/venv deps → "ComfyUI server not reachable".

Safe approach:
  - install krea2.py (+ qwen3vl.py if missing) under text_encoders
  - add "krea2" to CLIPLoader type list in nodes.py (string only)
  - do NOT hard-import krea2 from sd.py at module load (boot risk)
  - product load uses custom node PPKrea2CLIPLoader (lazy import)
"""
from __future__ import annotations

import os
import re
import shutil
import urllib.request

ROOT = "/comfyui"
TE = os.path.join(ROOT, "comfy", "text_encoders")
NODES = os.path.join(ROOT, "nodes.py")
VENDOR = "/comfyui/custom_nodes/pp_krea2/krea2_te.py"
RAW = "https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master"


def fetch(url: str, dest: str) -> None:
    print("fetch", url, "->", dest)
    urllib.request.urlretrieve(url, dest)
    print("ok", os.path.getsize(dest), "bytes")


def ensure_te_files() -> None:
    os.makedirs(TE, exist_ok=True)
    krea_dst = os.path.join(TE, "krea2.py")
    if os.path.isfile(VENDOR):
        shutil.copy2(VENDOR, krea_dst)
        print("krea2 from vendor", krea_dst, os.path.getsize(krea_dst))
    elif not os.path.isfile(krea_dst):
        fetch(f"{RAW}/comfy/text_encoders/krea2.py", krea_dst)
    else:
        print("krea2 already present")

    qwen = os.path.join(TE, "qwen3vl.py")
    if not os.path.isfile(qwen):
        # also try vendored copy next to custom node
        vend_q = "/comfyui/custom_nodes/pp_krea2/qwen3vl.py"
        if os.path.isfile(vend_q):
            shutil.copy2(vend_q, qwen)
            print("qwen3vl from vendor")
        else:
            fetch(f"{RAW}/comfy/text_encoders/qwen3vl.py", qwen)
    else:
        print("qwen3vl already present")


def patch_nodes_type_list() -> None:
    if not os.path.isfile(NODES):
        print("nodes.py missing — skip type list")
        return
    t = open(NODES, encoding="utf-8", errors="replace").read()
    if '"krea2"' in t or "'krea2'" in t:
        print("nodes.py already has krea2 type")
        return
    t2, n = re.subn(r'("qwen_image")', r'\1, "krea2"', t, count=1)
    if n == 0:
        t2, n = re.subn(r'("stable_diffusion")', r'\1, "krea2"', t, count=1)
    if n:
        open(NODES, "w", encoding="utf-8").write(t2)
        print("nodes.py: added krea2 to CLIPLoader type list")
    else:
        print("nodes.py: type list anchor not found (PPKrea2CLIPLoader still works)")


def main() -> None:
    ensure_te_files()
    patch_nodes_type_list()
    assert os.path.isfile(os.path.join(TE, "krea2.py")), "krea2.py missing"
    assert os.path.isfile("/comfyui/custom_nodes/pp_krea2/__init__.py"), "pp_krea2 missing"
    print("surgical_krea2_ok")


if __name__ == "__main__":
    main()
