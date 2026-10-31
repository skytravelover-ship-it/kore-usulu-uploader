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
    m = get(s["media_id"], fields="like_count,comments_count,timestamp")
    print(f"\n[{pid}] 좋아요 {m.get('like_count')} / 댓글 {m.get('comments_count')} / {m.get('timestamp')}")
    for metric in ["reach", "views", "saved", "shares", "total_interactions"]:
        r = get(f"{s['media_id']}/insights", metric=metric)
        if "error" in r:
            print(f"   {metric}: 조회 실패 {r['error'][:160]}")
        else:
            print(f"   {metric}: {r['data'][0]['values'][0]['value']}")
