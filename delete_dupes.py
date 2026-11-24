#!/usr/bin/env python3
"""One-off cleanup: delete duplicate copies of the 10-sebae carousel (approved by Jong, 2026-11-24).

Deletes only media that (1) is a CAROUSEL_ALBUM, (2) has exactly the 10-sebae caption,
(3) is not recorded in state.json. Everything else is left alone. DRY_RUN=1 only lists.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN, USER = os.environ["IG_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
BASE = f"https://{os.environ.get('IG_API_HOST', 'graph.instagram.com')}/v23.0"
DRY = os.environ.get("DRY_RUN", "1") != "0"
EXPECT = 41


def call(method, path, **params):
    params["access_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300]}


caption = (HERE / "posts/10-sebae/caption.txt").read_text(encoding="utf-8").strip()
state = json.loads((HERE / "state.json").read_text())
keep = {s["media_id"] for s in state.values() if s.get("media_id")}

media, after = [], None
while True:
    p = dict(fields="id,caption,timestamp,media_type,permalink", limit=100)
    if after:
        p["after"] = after
    r = call("GET", f"{USER}/media", **p)
    if "error" in r:
        raise SystemExit(f"목록 조회 실패 {r['error']}")
    media += r.get("data", [])
    after = r.get("paging", {}).get("cursors", {}).get("after") if r.get("paging", {}).get("next") else None
    if not after:
        break

targets = [m for m in media if m.get("media_type") == "CAROUSEL_ALBUM"
           and (m.get("caption") or "").strip() == caption and m["id"] not in keep]
print(f"전체 {len(media)}개 / 보존 기록 {len(keep)}개 / 삭제 대상 {len(targets)}개 (예상 {EXPECT})")
if len(targets) != EXPECT:
    raise SystemExit("삭제 대상 수가 예상과 달라 중단")
ok = fail = 0
for m in sorted(targets, key=lambda m: m["timestamp"]):
    if DRY:
        print(f"[모의] {m['id']} {m['timestamp']} {m['permalink']}")
        continue
    r = call("DELETE", m["id"])
    if r.get("success"):
        ok += 1
        print(f"삭제 {m['id']} {m['timestamp']}")
    else:
        fail += 1
        print(f"삭제 실패 {m['id']} {json.dumps(r, ensure_ascii=False)[:250]}")
        if fail >= 3 and ok == 0:
            raise SystemExit("연속 실패로 중단 (API가 삭제를 지원하지 않는 것으로 보임)")
print(f"결과: 삭제 {ok} / 실패 {fail} / 모의 {DRY}")
