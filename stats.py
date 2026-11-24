#!/usr/bin/env python3
"""Print account and per-post numbers for published posts (read only)."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN = os.environ["IG_ACCESS_TOKEN"]
USER = os.environ["IG_USER_ID"]
BASE = f"https://{os.environ.get('IG_API_HOST', 'graph.instagram.com')}/v23.0"


def get(path, **params):
    params["access_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300]}


acct = get(USER, fields="username,followers_count,follows_count,media_count")
print("계정:", json.dumps(acct, ensure_ascii=False))

state = json.loads((HERE / "state.json").read_text()) if (HERE / "state.json").exists() else {}
for pid, s in state.items():
    if not s.get("media_id"):
        print(f"\n[{pid}] ⛔ 게시 확인 안 됨: {s.get('status')} {s.get('error', '')[:120]}")
        continue
    m = get(s["media_id"], fields="like_count,comments_count,timestamp")
    print(f"\n[{pid}] 좋아요 {m.get('like_count')} / 댓글 {m.get('comments_count')} / {m.get('timestamp')}")
    for metric in ["reach", "views", "saved", "shares", "total_interactions"]:
        r = get(f"{s['media_id']}/insights", metric=metric)
        if "error" in r:
            print(f"   {metric}: 조회 실패 {r['error'][:160]}")
        else:
            print(f"   {metric}: {r['data'][0]['values'][0]['value']}")

# Audit: compare what is really on the account with what state.json says.
media, path, params = [], f"{USER}/media", dict(fields="id,caption,permalink,timestamp,media_type", limit=100)
while path:
    r = get(path, **params)
    if "error" in r:
        print("실제 게시물 조회 실패", r["error"][:200])
        break
    media += r.get("data", [])
    after = r.get("paging", {}).get("cursors", {}).get("after") if r.get("paging", {}).get("next") else None
    path, params = (path, dict(params, after=after)) if after else (None, params)
known = {s["media_id"]: pid for pid, s in state.items() if s.get("media_id")}
print(f"\n== 감사: 실제 게시물 {len(media)}개 / 기록된 게시물 {len(known)}개")
groups = {}
for m in media:
    key = (m.get("media_type"), (m.get("caption") or "").strip()[:80])
    groups.setdefault(key, []).append(m)
for (mtype, cap), items in groups.items():
    extra = [m for m in items if m["id"] not in known]
    if len(items) > 1 or extra:
        print(f"⚠ 중복/미기록 {len(items)}개 [{mtype}] {cap[:40]!r}")
        for m in sorted(items, key=lambda m: m["timestamp"]):
            print(f"   AUDIT {m['id']} {m['timestamp']} {m['permalink']} {'기록:' + known[m['id']] if m['id'] in known else '미기록'}")
if len(media) == len(known) and all(len(v) == 1 for v in groups.values()):
    print("감사 통과: 중복 없음")
