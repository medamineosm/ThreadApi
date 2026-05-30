# Threads Keyword Search POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that calls Threads keyword search, paginates, deduplicates by id, logs oldest date per page, and stops when results are older than Jan 1 of the current year (UTC).

**Architecture:** A single script (`fetch_threads.py`) with small helper functions for building params, fetching pages, parsing timestamps, and aggregating unique items. A pytest suite uses mocked HTTP responses to validate pagination, deduplication, and stop conditions without network calls.

**Tech Stack:** Python 3, `requests`, `pytest`

---

## File Structure

- Create: `fetch_threads.py` — CLI entrypoint and fetch logic.
- Create: `requirements.txt` — runtime dependencies (`requests`).
- Create: `tests/test_fetch_threads.py` — unit tests for pagination, dedupe, and stop conditions.

---

### Task 1: Add tests for pagination, dedupe, and stop conditions

**Files:**
- Create: `tests/test_fetch_threads.py`

- [ ] **Step 1: Write failing tests**

```python
import json
from datetime import datetime, timezone

import fetch_threads


def make_item(item_id, ts):
    return {
        "id": item_id,
        "timestamp": ts,
    }


def test_dedup_and_pagination_stop_at_cutoff(monkeypatch):
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    page1 = {
        "data": [
            make_item("1", "2026-02-01T00:00:00+0000"),
            make_item("2", "2026-01-15T00:00:00+0000"),
        ],
        "paging": {"next": "https://example.com/page2"},
    }
    page2 = {
        "data": [
            make_item("2", "2026-01-15T00:00:00+0000"),
            make_item("3", "2025-12-31T23:59:59+0000"),
        ],
        "paging": {"next": "https://example.com/page3"},
    }

    responses = [page1, page2]
    calls = []

    def fake_get(url, params=None):
        calls.append(url)
        data = responses.pop(0)

        class Resp:
            status_code = 200

            def json(self_inner):
                return data

            text = json.dumps(data)

        return Resp()

    results = fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=0,
        until=0,
        limit=100,
        access_token="token",
        cutoff_date=cutoff,
        request_get=fake_get,
        log_fn=lambda *_: None,
    )

    ids = sorted([item["id"] for item in results])
    assert ids == ["1", "2", "3"]
    assert calls == [fetch_threads.BASE_URL, "https://example.com/page2"]


def test_parse_timestamp_accepts_z_suffix():
    dt = fetch_threads.parse_timestamp("2026-02-01T00:00:00Z")
    assert dt.tzinfo is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch_threads.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetch_threads'` or missing functions.

- [ ] **Step 3: Commit**

```bash
git add tests/test_fetch_threads.py
git commit -m "test: add pagination and cutoff cases"
```

---

### Task 2: Implement fetch logic and CLI

**Files:**
- Create: `fetch_threads.py`

- [ ] **Step 1: Implement minimal code to pass tests**

```python
import argparse
import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests

BASE_URL = "https://graph.threads.net/v1.0/keyword_search"

FIELDS = (
    "id,media_product_type,media_type,media_url,permalink,username,text,timestamp,shortcode,"
    "thumbnail_url,children,children.media_url,children.media_type,children.permalink,"
    "children.text,is_quote_post,link_attachment_url,gif_url,has_replies,is_reply"
)


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Threads sometimes returns +0000 without colon
        if value.endswith("+0000"):
            return datetime.fromisoformat(value[:-5] + "+00:00")
        raise


def build_params(keyword: str, since: int, until: int, limit: int, access_token: str) -> Dict[str, str]:
    return {
        "q": keyword,
        "search_mode": "KEYWORD",
        "search_type": "RECENT",
        "since": str(since),
        "until": str(until),
        "limit": str(limit),
        "fields": FIELDS,
        "access_token": access_token,
    }


def collect_keyword_search(
    keyword: str,
    since: int,
    until: int,
    limit: int,
    access_token: str,
    cutoff_date: datetime,
    request_get: Callable = requests.get,
    log_fn: Callable[[str], None] = print,
) -> List[Dict]:
    seen_ids = set()
    results: List[Dict] = []
    next_url: Optional[str] = BASE_URL
    params = build_params(keyword, since, until, limit, access_token)
    page = 0

    while next_url:
        page += 1
        resp = request_get(next_url, params=params if next_url == BASE_URL else None)
        if resp.status_code != 200:
            raise RuntimeError(f"API error {resp.status_code}: {resp.text}")
        payload = resp.json()
        data = payload.get("data", [])

        oldest_dt = None
        for item in data:
            item_id = item.get("id")
            ts = item.get("timestamp")
            if not item_id or not ts:
                continue
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append(item)
            dt = parse_timestamp(ts)
            if oldest_dt is None or dt < oldest_dt:
                oldest_dt = dt

        if oldest_dt:
            log_fn(f"page={page} oldest_in_page={oldest_dt.date().isoformat()}")
            if oldest_dt < cutoff_date:
                log_fn(f"stop=older_than_cutoff cutoff={cutoff_date.date().isoformat()}")
                break

        next_url = payload.get("paging", {}).get("next")
        params = None

    return results


def jan_1_current_year_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, 1, 1, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--since", type=int, default=None)
    parser.add_argument("--until", type=int, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc)
    cutoff = jan_1_current_year_utc()
    since = args.since if args.since is not None else int(cutoff.timestamp())
    until = args.until if args.until is not None else int(now.timestamp())

    access_token = "THAA0ZBjBbhZAz1BUVFBeGxoZAmhLWF9mMmpyYTQ5T0Mzblo2bElSYkNDQ3FYQW44QTNhb3pnTjktc1hGcUdXNTl1bFBPZA1hjLXRXT0hCZAGIxc09DdEdDZAjhfb0dZAOEI2ZATB5ZAThiMWJkRk1MLS1Sa2xuZAE9yeWFtSy1OM2QtZAVZAuNW5aZAwZDZD"

    results = collect_keyword_search(
        keyword=args.keyword,
        since=since,
        until=until,
        limit=args.limit,
        access_token=access_token,
        cutoff_date=cutoff,
    )

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print(json.dumps(results))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_fetch_threads.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add fetch_threads.py
git commit -m "feat: add threads keyword search cli"
```

---

### Task 3: Add runtime dependency list

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Add requirements**

```text
requests>=2.31.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add python requirements"
```

---

## Self-Review Checklist

- Spec coverage: CLI args, pagination, dedupe, log oldest date, stop at cutoff, hard-coded token, output JSON.
- No placeholders: all steps include code or exact commands.
- Type consistency: helper function names match across tests and implementation.
