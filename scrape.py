#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""team.imweb.me 블로그 글 목록을 모아 posts.json 으로 저장한다.

GitHub Actions 가 주기적으로 실행한다. 로컬에서 바로 돌려도 된다:
    python3 scrape.py
"""

import html
import json
import pathlib
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://team.imweb.me"
BOARDS = [
    ("blog_people", "피플"),
    ("blog-culture", "컬쳐"),
    ("blog-insight", "인사이트"),
]
MAX_PAGE = 40
KST = timezone(timedelta(hours=9))
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
}

# 목록 페이지의 카드 1장 = <a class="post_link_wrap ...> ... <div class="title title-block">제목</div>
CARD_RE = re.compile(
    r'<a class="post_link_wrap[^"]*"\s*href="[^"]*?idx=(?P<idx>\d+)[^"]*".*?'
    r'(?:background-image:\s*url\(&quot;(?P<thumb>[^&]*?)&quot;\).*?)?'
    r'<div class="title title-block">(?P<title>.*?)</div>',
    re.S,
)
CAT_RE = re.compile(r'<em[^>]*padding-right:5px[^>]*>(.*?)</em>', re.S)
TAG_RE = re.compile(r'<[^>]+>', re.S)


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def strip_tags(s):
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    return html.unescape(TAG_RE.sub('', s)).strip()


def parse_list(doc, board, board_label):
    out = []
    for m in CARD_RE.finditer(doc):
        raw = m.group("title")
        cat = CAT_RE.search(raw)
        category = (strip_tags(cat.group(1)) if cat else "") or board_label
        title = re.sub(r'^공지\s*', '', strip_tags(CAT_RE.sub('', raw, count=1))).strip()
        if not title:
            continue
        thumb = html.unescape(m.group("thumb") or "")
        d = re.search(r'/thumbnail/(\d{4})(\d{2})(\d{2})/', thumb)
        out.append({
            "idx": m.group("idx"),
            "board": board,
            "category": category,
            "title": title,
            "thumb": thumb,
            "date": f"{d.group(1)}.{d.group(2)}.{d.group(3)}" if d else "",
            "url": f"{BASE}/{board}/?idx={m.group('idx')}&bmode=view",
        })
    return out


def scrape():
    posts, seen = [], set()
    for board, label in BOARDS:
        for page in range(1, MAX_PAGE + 1):
            url = f"{BASE}/{board}" + (f"?page={page}" if page > 1 else "")
            doc = fetch(url)
            found = parse_list(doc, board, label)
            fresh = [p for p in found if p["idx"] not in seen]
            for p in fresh:
                seen.add(p["idx"])
            posts.extend(fresh)
            print(f"  {board} p{page}: {len(found)}건 (신규 {len(fresh)})")
            if not fresh:
                break
            time.sleep(0.2)
    posts.sort(key=lambda p: int(p["idx"]), reverse=True)
    return posts


def main():
    posts = scrape()
    # 수집이 통째로 실패했으면 기존 posts.json 을 덮어쓰지 않는다
    if len(posts) < 5:
        print(f"수집 결과가 {len(posts)}건뿐이라 중단합니다 (블로그 구조 변경 의심)", file=sys.stderr)
        sys.exit(1)

    out = pathlib.Path(__file__).parent / "posts.json"
    old = None
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8")).get("posts")
        except Exception:
            pass
    if old == posts:
        print(f"변경 없음 ({len(posts)}건)")
        return

    out.write_text(json.dumps({
        "updated_at": datetime.now(KST).strftime("%Y.%m.%d %H:%M"),
        "count": len(posts),
        "posts": posts,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"갱신 완료: {len(posts)}건")


if __name__ == "__main__":
    main()
