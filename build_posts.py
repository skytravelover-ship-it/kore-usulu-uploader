#!/usr/bin/env python3
"""Copy the rendered card PNGs into posts/<id>/ as JPEGs (Instagram API accepts JPEG only).

Run after re-rendering cards:  python3 build_posts.py
Captions (caption.txt) and first comments (comment.txt) are edited by hand in posts/<id>/.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # folder that holds 카드뉴스/


def main():
    cfg = json.loads((HERE / "posts.json").read_text(encoding="utf-8"))
    for p in cfg["posts"]:
        src = ROOT / p["src"]
        pngs = sorted(src.glob(f"{p['prefix']}[0-9][0-9].png"))
        if not pngs:
            sys.exit(f"[{p['id']}] PNG 없음: {src}")
        if len(pngs) > 10:
            sys.exit(f"[{p['id']}] 캐러셀은 최대 10장입니다 ({len(pngs)}장)")
        out = HERE / "posts" / p["id"]
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("*.jpg"):
            old.unlink()
        for i, png in enumerate(pngs, 1):
            jpg = out / f"{i:02d}.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92",
                            str(png), "--out", str(jpg)], check=True, capture_output=True)
        print(f"[{p['id']}] {len(pngs)}장 → {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
