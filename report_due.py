#!/usr/bin/env python3
"""Find posts that passed the 2-hour mark and are not reported yet, and fetch their numbers.

  python3 report_due.py           # prints NONE, or the due posts plus fresh stats for every post
  python3 report_due.py --mark A B  # record A and B as reported

Stats come from the read-only stats.yml workflow (the token lives in GitHub secrets).
.reported.json stays local (gitignored).
"""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTED = HERE / ".reported.json"
TR = timezone(timedelta(hours=3))


def sh(*cmd):
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, check=True).stdout


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main():
    reported = load(REPORTED, [])
    if sys.argv[1:2] == ["--mark"]:
        REPORTED.write_text(json.dumps(sorted(set(reported) | set(sys.argv[2:])), indent=2) + "\n")
        print("기록:", " ".join(sys.argv[2:]))
        return

    sh("git", "fetch", "-q", "origin", "main")
    state = json.loads(sh("git", "show", "origin/main:state.json"))
    posts = json.loads(sh("git", "show", "origin/main:posts.json")).get("posts", [])
    titles = {p["id"]: p.get("title", p["id"]) for p in posts}
    now = datetime.now(timezone.utc)
    due = []
    for pid, s in state.items():
        at = datetime.fromisoformat(s["published_at"])
        if pid not in reported and now - at >= timedelta(hours=2):
            due.append((pid, at, s))
    if not due:
        print("NONE")
        return

    print("== 보고할 게시물")
    for pid, at, s in due:
        hours = (now - at).total_seconds() / 3600
        print(f"{pid} | {titles.get(pid, pid)} | 게시 {at.astimezone(TR):%m/%d %H:%M} 터키 | 경과 {hours:.1f}시간 | {s.get('permalink')}")

    t0 = datetime.now(timezone.utc) - timedelta(seconds=5)
    sh("gh", "workflow", "run", "stats.yml", "--ref", "main")
    run_id = None
    for _ in range(30):
        time.sleep(4)
        runs = json.loads(sh("gh", "run", "list", "-w", "stats.yml", "-L", "3", "--json", "databaseId,createdAt"))
        new = [r for r in runs if datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")) >= t0]
        if new:
            run_id = str(new[0]["databaseId"])
            break
    if not run_id:
        print("통계 실행을 찾지 못함")
        return
    subprocess.run(["gh", "run", "watch", run_id, "--exit-status"], cwd=HERE, capture_output=True)
    log = sh("gh", "run", "view", run_id, "--log")
    print(f"\n== 통계 (실행 {run_id}, {datetime.now(TR):%m/%d %H:%M} 터키)")
    no_perm = False
    for line in log.splitlines():
        text = re.sub(r"^.*?\d{4}-\d\d-\d\dT[\d:.]+Z ", "", line)
        if text.startswith("계정:") or re.match(r"^\[[\w-]+\] 좋아요", text):
            print(text[:200])
        elif "조회 실패" in text and "(#10)" in text:
            no_perm = True
        elif re.match(r"^\s+(reach|views|saved|shares|total_interactions): \d", text):
            print(text)
    if no_perm:
        print("조회수·도달·저장·공유: 통계 권한 없음(#10), 토큰 교체 전까지 접근 불가")

if __name__ == "__main__":
    main()
