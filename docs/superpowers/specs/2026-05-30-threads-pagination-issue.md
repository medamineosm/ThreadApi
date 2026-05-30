# Threads Keyword Search Pagination Behavior and Mitigations

## Summary
- Observed: `keyword_search` paging returns repeating `paging.next` URLs, pages overlap, and timestamps bounce (non-chronological, relevance-ranked window). Without safeguards, the client can loop endlessly over similar results.
- Goal: Fetch distinct data safely, avoid infinite/overlapping pagination, and surface clear diagnostics.
- Implemented mitigations: repeat-cursor detection and stop, max-pages guard, per-page diagnostics (min/max timestamps + cursor hash), time-sliced crawling with dedupe across slices, continued raw NDJSON streaming, and existing rate limiting/429 handling.

## Evidence (from `threads_20260530_160511.json` run)
- 60 pages captured; all `paging.next` shared the same prefix → no real cursor advancement.
- Global timestamps: min `2026-05-06T15:49:53Z`, max `2026-05-07T19:57:40Z`.
- 25 "bounce" events where per-page min timestamp increased vs. previous page → pages are not chronological.
- NDJSON stream confirmed overlapping content across pages.

## Root Cause (inferred)
- Threads `keyword_search` appears to return a relevance-ranked window rather than strictly time-ordered results.
- Cursor pagination is not guaranteed to advance; repeated cursors cause overlapping page windows.
- No alternative server-side paging mechanism is documented for this endpoint.

## Mitigations Implemented
- **Repeat-cursor stop:** Track seen `paging.next`; on repeat, log `repeat_cursor cursor_hash=<hash>` and break.
- **Max-pages guard:** `--max-pages` (default 100) logs `stop=max_pages` and stops to prevent infinite loops.
- **Per-page diagnostics:** Log `page=N min_ts=... max_ts=... cursor_hash=...` to make overlap visible.
- **Time-sliced crawling:** `--step-back-hours` (default 24) walks backward in fixed time slices, deduping IDs across slices; raw NDJSON streaming remains per page.
- **Raw streaming:** Still writes one raw page payload per line (NDJSON) to the timestamped output file; `saved_to=...` logs when the file opens.
- **Existing:** Rate limiting (`sleep_ms`), 429 backoff, ID dedupe, and timestamp window filtering remain in place.

## Operational Flow (Mermaid)
```mermaid
flowchart TD
  A[Start slice (since/until)] --> B[pace + rate-limit]
  B --> C[GET keyword_search]
  C -->|429| D[log rate_limit_hit; sleep; retry]
  C -->|non-200| E[fail: API error]
  C -->|200| F[append raw page; log min/max ts + cursor hash]
  F --> G{repeat cursor?}
  G -->|yes| H[log repeat_cursor; stop slice]
  G -->|no| I{page >= max_pages?}
  I -->|yes| J[log stop=max_pages; stop slice]
  I -->|no| K{oldest_ts < cutoff?}
  K -->|yes| L[log stop=older_than_cutoff; stop slice]
  K -->|no| M[next cursor]
  M --> B
  H & J & L --> N{more slices?}
  N -->|yes (step-back)| A
  N -->|no| O[finish]
```

## Usage Notes
- Default safeguards: `--max-pages 100`, `--step-back-hours 24`.
- Typical command: `python3 fetch_threads.py --keyword rolex --since <epoch> --until <epoch> --limit 10 --max-rps 2 --burst 1 --pretty --output-dir .`
- Raw pages stream to `threads_YYYYMMDD_HHMMSS.json` (NDJSON). Logs show per-page min/max and cursor hashes; repeats or max-page stops are logged explicitly.

## Limitations
- Still dependent on API quality; relevance ranking can return overlapping windows even within a slice.
- Smaller slices improve progression but increase request count; larger slices risk more overlap.
- No server-side guarantee for chronological paging; client safeguards are defensive rather than a true fix.

## Tuning Options
- Adjust `--step-back-hours` (e.g., 12h) to tighten slices.
- Adjust `--max-pages` per slice if needed.
- Monitor logs for `repeat_cursor` and min/max ts bounces to evaluate coverage.
