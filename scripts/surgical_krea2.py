#!/usr/bin/env python3
"""Surgical krea2 TE support without full Comfy overlay.

Product fail on first surgical image:
  cannot import name 'Qwen3VL_4BConfig' from 'comfy.text_encoders.llama'

Install a *matched* text_encoders subset from Comfy master (files + tokenizer
dirs krea2/qwen3vl need). Do NOT replace whole /comfyui/comfy (breaks /opt/venv).
"""
from __future__ import annotations

import os
import re
import shutil
import tarfile
import urllib.request

ROOT = "/comfyui"
TE = os.path.join(ROOT, "comfy", "text_encoders")
NODES = os.path.join(ROOT, "nodes.py")
TGZ = "/tmp/comfy_master_surgical.tgz"
URL = "https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.tar.gz"

# Matched set for Krea2 / Qwen3-VL-4B TE (no full comfy tree)
TE_FILES = (
    "krea2.py",
    "llama.py",
    "qwen3vl.py",
    "qwen_vl.py",
    "qwen35.py",
    "qwen_image.py",
)
TE_DIRS = (
    "llama_tokenizer",
    "qwen25_tokenizer",
    "qwen35_tokenizer",
)


def patch_nodes_type_list() -> None:
    if not os.path.isfile(NODES):
        print("nodes.py missing — skip")
        return
    t = open(NODES, encoding="utf-8", errors="replace").read()
    if '"krea2"' in t or "'krea2'" in t:
        print("nodes.py already has krea2")
        return
    t2, n = re.subn(r'("qwen_image")', r'\1, "krea2"', t, count=1)
    if n == 0:
        t2, n = re.subn(r'("stable_diffusion")', r'\1, "krea2"', t, count=1)
    if n:
        open(NODES, "w", encoding="utf-8").write(t2)
        print("nodes.py: added krea2 type")
    else:
        print("nodes.py: type list anchor not found")


def install_from_master_tarball() -> None:
    os.makedirs(TE, exist_ok=True)
    print("download", URL)
    urllib.request.urlretrieve(URL, TGZ)
    print("tarball", os.path.getsize(TGZ), "bytes")
    with tarfile.open(TGZ, "r:gz") as tf:
        # members under ComfyUI-master/comfy/text_encoders/
        prefix = None
        for m in tf.getmembers():
            if m.name.endswith("/comfy/text_encoders/krea2.py"):
                prefix = m.name[: -len("krea2.py")]
                break
        if not prefix:
            raise RuntimeError("krea2.py not found in tarball")
        print("prefix", prefix)

        for name in TE_FILES:
            member = prefix + name
            try:
                f = tf.extractfile(member)
            except KeyError:
                f = None
            if f is None:
                # try find
                hits = [x for x in tf.getmembers() if x.name.endswith("/text_encoders/" + name)]
                if not hits:
                    print("MISSING file in tarball", name)
                    continue
                f = tf.extractfile(hits[0])
                member = hits[0].name
            dest = os.path.join(TE, name)
            with open(dest, "wb") as out:
                out.write(f.read())
            print("installed", name, os.path.getsize(dest))

        for dname in TE_DIRS:
            dest_dir = os.path.join(TE, dname)
            # extract all members under text_encoders/<dname>/
            count = 0
            for m in tf.getmembers():
                marker = "/text_encoders/" + dname + "/"
                if marker not in m.name:
                    continue
                rel = m.name.split(marker, 1)[1]
                if not rel or m.isdir():
                    continue
                out_path = os.path.join(dest_dir, rel)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                src = tf.extractfile(m)
                if src is None:
                    continue
                with open(out_path, "wb") as out:
                    out.write(src.read())
                count += 1
            print("installed dir", dname, "files", count)

    try:
        os.remove(TGZ)
    except OSError:
        pass


def smoke_files() -> None:
    llama = open(os.path.join(TE, "llama.py"), encoding="utf-8", errors="replace").read()
    assert "Qwen3VL_4BConfig" in llama, "llama.py still missing Qwen3VL_4BConfig"
    krea = open(os.path.join(TE, "krea2.py"), encoding="utf-8", errors="replace").read()
    assert "def te(" in krea or "Krea2TEModel" in krea
    print("smoke_files_ok Qwen3VL_4BConfig present")


def main() -> None:
    install_from_master_tarball()
    patch_nodes_type_list()
    smoke_files()
    assert os.path.isfile("/comfyui/custom_nodes/pp_krea2/__init__.py")
    print("surgical_krea2_ok")


if __name__ == "__main__":
    main()
