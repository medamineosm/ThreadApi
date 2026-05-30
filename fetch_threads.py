import argparse
import hashlib
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set, Tuple

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


def build_output_path(output_dir: str, now: datetime) -> Path:
    dirname = Path(output_dir or ".")
    filename = f"threads_{now.strftime('%Y%m%d_%H%M%S')}.json"
    return dirname / filename


def write_results_file(path: Path, results: List[Dict], pretty: bool, log_fn: Callable[[str], None]) -> None:
    text = json.dumps(results, indent=2) if pretty else json.dumps(results)
    path.write_text(text)
    log_fn(f"saved_to={path}")


def write_raw_results_file(
    path: Path,
    raw_pages: List[Dict],
    collected_at: datetime,
    pretty: bool,
    log_fn: Callable[[str], None],
) -> None:
    payload = {
        "collected_at": collected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": raw_pages,
    }
    text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
    path.write_text(text)
    log_fn(f"saved_to={path}")


def collect_keyword_search(
    keyword: str,
    since: int,
    until: int,
    limit: int,
    access_token: str,
    cutoff_date: datetime,
    request_get: Callable = requests.get,
    log_fn: Callable[[str], None] = print,
    max_rps: float = 2.0,
    burst: int = 1,
    time_fn: Callable[[], float] = None,
    sleep_fn: Callable[[float], None] = None,
    raw_stream_path: Optional[Path] = None,
    raw_stream_mode: str = "w",
    max_pages: Optional[int] = 100,
    seen_ids: Optional[Set[str]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    time_fn = time_fn or time.time
    sleep_fn = sleep_fn or time.sleep

    tokens = 0.0
    last_time = time_fn()
    interval = 1.0 / max_rps if max_rps > 0 else 0.0

    stream_handle = None
    if raw_stream_path is not None:
        raw_stream_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids = seen_ids if seen_ids is not None else set()
    seen_cursors: Set[str] = set()
    results: List[Dict] = []
    raw_pages: List[Dict] = []
    next_url: Optional[str] = BASE_URL
    params = build_params(keyword, since, until, limit, access_token)
    page = 0
    window_start = datetime.fromtimestamp(since, timezone.utc)
    window_end = datetime.fromtimestamp(until, timezone.utc)

    try:
        if raw_stream_path is not None:
            stream_handle = raw_stream_path.open(raw_stream_mode, encoding="utf-8")
            if raw_stream_mode == "w":
                log_fn(f"saved_to={raw_stream_path}")

        def pace() -> None:
            nonlocal tokens, last_time
            now = time_fn()
            elapsed = max(0.0, now - last_time)
            if interval > 0:
                tokens = min(float(burst), tokens + (elapsed / interval))
            last_time = now
            if tokens >= 1.0:
                tokens -= 1.0
                return
            if interval > 0:
                sleep_for = (1.0 - tokens) * interval
                log_fn(f"sleep_ms={int(sleep_for * 1000)}")
                sleep_fn(sleep_for)
                tokens = 0.0

        while next_url:
            if next_url in seen_cursors:
                log_fn(f"repeat_cursor cursor_hash={hashlib.sha1(next_url.encode()).hexdigest()[:8]}")
                break
            seen_cursors.add(next_url)

            if max_pages is not None and page >= max_pages:
                log_fn(f"stop=max_pages pages={page}")
                break

            page += 1
            pace()
            resp = request_get(next_url, params=params if next_url == BASE_URL else None)
            if resp.status_code == 429:
                log_fn("rate_limit_hit")
                sleep_fn(2.0)
                continue
            if resp.status_code != 200:
                raise RuntimeError(f"API error {resp.status_code}: {resp.text}")
            payload = resp.json()
            if stream_handle:
                stream_handle.write(json.dumps(payload))
                stream_handle.write("\n")
                stream_handle.flush()
            raw_pages.append(payload)
            data = payload.get("data", [])

            oldest_dt = None
            dts = []
            for item in data:
                item_id = item.get("id")
                ts = item.get("timestamp")
                if not item_id or not ts:
                    continue
                dt = parse_timestamp(ts)
                if oldest_dt is None or dt < oldest_dt:
                    oldest_dt = dt
                dts.append(dt)
                if dt < window_start or dt > window_end:
                    continue
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    results.append(item)

            if oldest_dt:
                max_dt = max(dts) if dts else None
                cursor_hash = hashlib.sha1(next_url.encode()).hexdigest()[:8]
                log_fn(
                    f"page={page} min_ts={oldest_dt.isoformat()} max_ts={(max_dt.isoformat() if max_dt else '')} cursor_hash={cursor_hash}"
                )
                if oldest_dt < cutoff_date:
                    log_fn(f"stop=older_than_cutoff cutoff={cutoff_date.date().isoformat()}")
                    break

            next_url = payload.get("paging", {}).get("next")
            params = None

    finally:
        if stream_handle:
            stream_handle.close()

    return results, raw_pages


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
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-rps", type=float, default=2.0)
    parser.add_argument("--burst", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--step-back-hours", type=int, default=24)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc)
    cutoff = jan_1_current_year_utc()
    since = args.since if args.since is not None else int(cutoff.timestamp())
    until = args.until if args.until is not None else int(now.timestamp())

    output_path = build_output_path(args.output_dir, now)
    if args.output_dir and not output_path.parent.exists():
        raise RuntimeError(f"output_dir_not_found={output_path.parent}")

    access_token = "THAA0ZBjBbhZAz1BUVFBeGxoZAmhLWF9mMmpyYTQ5T0Mzblo2bElSYkNDQ3FYQW44QTNhb3pnTjktc1hGcUdXNTl1bFBPZA1hjLXRXT0hCZAGIxc09DdEdDZAjhfb0dZAOEI2ZATB5ZAThiMWJkRk1MLS1Sa2xuZAE9yeWFtSy1OM2QtZAVZAuNW5aZAwZDZD"

    all_results: List[Dict] = []
    all_raw_pages: List[Dict] = []
    seen_ids: Set[str] = set()

    step_hours = args.step_back_hours if args.step_back_hours is not None else 0
    step_seconds = step_hours * 3600

    if step_hours and step_hours > 0:
        current_until = until
        first_slice = True
        while current_until > since:
            window_since = max(since, current_until - step_seconds)
            results, raw_pages = collect_keyword_search(
                keyword=args.keyword,
                since=int(window_since),
                until=int(current_until),
                limit=args.limit,
                access_token=access_token,
                cutoff_date=cutoff,
                max_rps=args.max_rps,
                burst=args.burst,
                raw_stream_path=output_path,
                raw_stream_mode="w" if first_slice else "a",
                max_pages=args.max_pages,
                seen_ids=seen_ids,
            )
            all_results.extend(results)
            all_raw_pages.extend(raw_pages)
            seen_ids.update({item["id"] for item in results})
            current_until = window_since
            first_slice = False
    else:
        results, raw_pages = collect_keyword_search(
            keyword=args.keyword,
            since=since,
            until=until,
            limit=args.limit,
            access_token=access_token,
            cutoff_date=cutoff,
            max_rps=args.max_rps,
            burst=args.burst,
            raw_stream_path=output_path,
            raw_stream_mode="w",
            max_pages=args.max_pages,
            seen_ids=seen_ids,
        )
        all_results.extend(results)
        all_raw_pages.extend(raw_pages)

    final_results = all_results
    if args.pretty:
        print(json.dumps(final_results, indent=2))
    else:
        print(json.dumps(final_results))


if __name__ == "__main__":
    main()
