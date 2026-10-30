#!/usr/bin/env python3
"""Publish due carousel posts to Instagram via the official Graph API.

Usage
  python3 publish.py --check            # validate files and show the schedule (no network)
  python3 publish.py --dry-run          # show what would be published now (no network)
  python3 publish.py                    # publish every due, not-yet-published post
  python3 publish.py --only 01-joriwon  # publish one post now, ignoring its time

Environment
  IG_USER_ID       Instagram professional account ID
  IG_ACCESS_TOKEN  long-lived access token (Instagram API with Instagram Login)
  IMAGE_BASE_URL   public URL where posts/ is served, e.g.
                   https://raw.githubusercontent.com/<user>/<repo>/main/posts
  IG_API_HOST      optional, default graph.instagram.com (use graph.facebook.com for Facebook Login)
  IG_API_VERSION   optional, default v23.0

state.json records what was published, so a post is never published twice.
"""
import argparse
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
MAX_JPEG = 8 * 1024 * 1024
MAX_LATE_HOURS = 6  # never auto-publish a post more than this late (protects against a wrong launch_date)


def load_cfg():
    return json.loads((HERE / "posts.json").read_text(encoding="utf-8"))


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tz(cfg):
    sign = 1 if cfg["timezone_utc_offset"][0] == "+" else -1
    h, m = cfg["timezone_utc_offset"][1:].split(":")
    return timezone(sign * timedelta(hours=int(h), minutes=int(m)))


def due_at(cfg, post):
    if not cfg.get("launch_date"):
        return None
    d = datetime.strptime(cfg["launch_date"], "%Y-%m-%d").date() + timedelta(days=post["day"])
    hh, mm = post["time"].split(":")
    return datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=tz(cfg))


def jpeg_size(path):
    """Return (width, height) of a JPEG by reading its SOF marker."""
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("JPEG 아님")
        while True:
            marker, size = struct.unpack(">2sH", f.read(4))
            if marker[1] in (0xC0, 0xC1, 0xC2):
                f.read(1)
                h, w = struct.unpack(">HH", f.read(4))
                return w, h
            f.read(size - 2)


def check_post(post):
    """Return (images, caption, comment, problems)."""
    folder = HERE / "posts" / post["id"]
    images = sorted(folder.glob("*.jpg"))
    problems = []
    if not 2 <= len(images) <= 10:
        problems.append(f"이미지 {len(images)}장 (2~10장이어야 함)")
    for img in images:
        if img.stat().st_size > MAX_JPEG:
            problems.append(f"{img.name} 8MB 초과")
        w, h = jpeg_size(img)
        if not 0.8 - 1e-3 <= w / h <= 1.91:
            problems.append(f"{img.name} 비율 {w}x{h} (4:5~1.91:1)")
    cap_file, com_file = folder / "caption.txt", folder / "comment.txt"
    caption = cap_file.read_text(encoding="utf-8").strip() if cap_file.exists() else ""
    comment = com_file.read_text(encoding="utf-8").strip() if com_file.exists() else ""
    if not caption:
        problems.append("caption.txt 없음")
    if len(caption) > 2200:
        problems.append(f"캡션 {len(caption)}자 (2,200자 이하)")
    if caption.count("#") > 30:
        problems.append("해시태그 30개 초과")
    return images, caption, comment, problems


class Api:
    def __init__(self):
        self.user = os.environ["IG_USER_ID"]
        self.token = os.environ["IG_ACCESS_TOKEN"]
        host = os.environ.get("IG_API_HOST", "graph.instagram.com")
        self.base = f"https://{host}/{os.environ.get('IG_API_VERSION', 'v23.0')}"

    def call(self, method, path, **params):
        params["access_token"] = self.token
        data = urllib.parse.urlencode(params).encode()
        url = f"{self.base}/{path}"
        if method == "GET":
            req = urllib.request.Request(f"{url}?{data.decode()}")
        else:
            req = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path} → {e.code} {e.read().decode()[:500]}") from None

    def wait_ready(self, container):
        for _ in range(30):
            status = self.call("GET", container, fields="status_code").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"컨테이너 {container} 상태 {status}")
            time.sleep(5)
        raise RuntimeError(f"컨테이너 {container} 준비 시간 초과")

    def quota_left(self):
        r = self.call("GET", f"{self.user}/content_publishing_limit", fields="config,quota_usage")
        d = (r.get("data") or [{}])[0]
        return d.get("config", {}).get("quota_total", 50) - d.get("quota_usage", 0)

    def publish_carousel(self, urls, caption, comment):
        children = []
        for u in urls:
            c = self.call("POST", f"{self.user}/media", image_url=u, is_carousel_item="true")["id"]
            self.wait_ready(c)
            children.append(c)
        parent = self.call("POST", f"{self.user}/media", media_type="CAROUSEL",
                           children=",".join(children), caption=caption)["id"]
        self.wait_ready(parent)
        media = self.call("POST", f"{self.user}/media_publish", creation_id=parent)["id"]
        comment_id = None
        if comment:
            comment_id = self.call("POST", f"{media}/comments", message=comment).get("id")
        link = self.call("GET", media, fields="permalink").get("permalink")
        return media, comment_id, link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()

    cfg, state = load_cfg(), load_state()
    now = datetime.now(timezone.utc)
    bad = False
    todo = []
    for p in cfg["posts"]:
        images, caption, comment, problems = check_post(p)
        when = due_at(cfg, p)
        done = p["id"] in state
        tag = "게시됨" if done else ("시각 미정" if when is None else ("대기" if when > now else "게시 시각 지남"))
        print(f"{p['id']:12} {len(images)}장  {when.strftime('%Y-%m-%d %H:%M') if when else '----'}  {tag}")
        for pr in problems:
            print(f"    ⚠ {pr}")
            bad = True
        if done:
            continue
        if a.only and p["id"] == a.only:
            todo.append((p, images, caption, comment, problems))
        elif not a.only and when and when <= now:
            if now - when > timedelta(hours=MAX_LATE_HOURS):
                print(f"    ⚠ 게시 시각에서 {MAX_LATE_HOURS}시간 넘게 지나 자동 게시하지 않음 (--only {p['id']} 로 수동 게시)")
            else:
                todo.append((p, images, caption, comment, problems))

    if a.check:
        sys.exit(1 if bad else 0)
    if not todo:
        print("지금 올릴 게시물 없음")
        return

    base = os.environ.get("IMAGE_BASE_URL", "<IMAGE_BASE_URL>").rstrip("/")
    api = None if a.dry_run else Api()
    if api and api.quota_left() < len(todo):
        sys.exit("오늘 게시 한도가 부족합니다")
    for p, images, caption, comment, problems in todo:
        if problems:
            print(f"[{p['id']}] 문제가 있어 건너뜀")
            continue
        urls = [f"{base}/{p['id']}/{img.name}" for img in images]
        if a.dry_run:
            print(f"\n[모의] {p['id']}: {len(urls)}장, 캡션 {len(caption)}자, 첫 댓글 {'있음' if comment else '없음'}")
            print("   " + urls[0])
            continue
        media, comment_id, link = api.publish_carousel(urls, caption, comment)
        state[p["id"]] = {"media_id": media, "comment_id": comment_id, "permalink": link,
                          "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        save_state(state)
        print(f"[{p['id']}] 게시 완료 {link}")


if __name__ == "__main__":
    main()
